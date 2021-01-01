#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Tallylight sollution for OBS and a Rasperry Pi
# - best used with obs studio mode
# - but should work also without studio, but will not react when
#   changing visibility of sources of a scene
# 
# Features:
# * configuration by real XML, not depenting on tag ordering
# * LEDs status can be configurted in dependence of scenes and/or sources
# * support unlimited amount of scene and sources
# * after startup LEDs will proactive be set conforming actual OBS status
#   (will not wait for first switch/preview event)
# * connection to OBS is monitored and will try to reconnect if lost
# * possible LEDs enabled conbinations: (LED color depends on
#   hardware configuration, ex: red for "in program", orange for "in preview")
#   A) basic: 
#      - CAM in programm => red LED enabled
#      - CAM in preview => orange LED enabled
#      in basic-mode any conbination is possible, also both LEDs on at the same time
#   B) max. 1 LED per CAM enabled:
#      same as (A), but in case a CAM is also "in preview", only the
#      "in program" LED will be enabled
#   C) max. 1 LED type enabled:
#      same as (B), but maximal 1 LED type will be enabled at the same time.
#      examples:
#      - CAM 1 in program AND CAM 2 in preview: only LED for CAM 1 will be enabled
#      - unknown scene/source in program AND CAM 1 in preview: CAM 1 LED shown
#      - CAM 1 and CAM 2 in program, CAM 3 in preview: CAM 1+2 will be enabled
#      - unknown scene/source in program AND CAM 1+2 in preview: CAM 1+2 LED shown

DEBUG = False  # additional debugging output
ONLY_ONE_LED_PER_CAM_ON = True  # Same CAM can not be preview and program at the same time
MAX_ONE_LED_ON = True  # maximal one LED enabled at the same time, program LED has priority

# Please define here the name of your XMLS config file
# (by default it is saved on the save path as the executable)
from os.path import abspath, dirname
XML_FILE = "{}/obstally.xml".format(dirname(abspath(__file__)))


from gpiozero import LED
from obswebsocket import obsws, events, requests
from xml.etree import ElementTree
import os
import sched
from time import time, sleep
from threading import Timer


def debug(*txt):
    if DEBUG:
        print(">> {}".format(txt[0] if len(txt) == 1 else txt))


class OBStally:
    ''' configuration attributes '''
    # the obswebsocket (host, port, pass)
    obs = {'host': None, 'port': None, 'pass': None, 'gpio_connected': None }
    # known OBS scenes (name, gpios, ...)
    scenes = {}
    # known OBS sources (name, gpios, ...)
    sources = {}

    ''' runtime changebled/status attributes '''
    # the websocket object
    ws = None
    # last activated LED for a the spefic type
    act_gpio = { 'program': None, 'preview': None }
    # actual connection status
    connected = False
    # timestamp in secons of last heartbeat (float)
    last_heartbeat = None

    '''
    INITIALISATION
    '''
    def __init__(self):
        """
        initialise the enviroment
        """
        debug("__init__()")
        # read xml an init leds based on config
        if not self.read_xml_config():
            return
        # OBS websocket initialisation
        self.initialise_leds()
        self.obs_connect()
        # prepare schedular to monitor connection
        Timer(1, self.check_connection, ()).start()
        # run endless
        self.run()

    def read_xml_config(self):
        """
        read the configuration from the XML-file and save the values
        to the dictionaries
        """
        def _readSubTags(root, tag, gpios):
            result = {}
            for s in root.findall(tag):
                content = {'name': "", "gpio": {}, 'led': {} }
                for child in s.findall('*'):
                    if "gpio" in child.tag:
                        nr = int(child.text)
                        if nr in gpios:
                            print("ERROR: GPIO {} can only be used once!".format(nr))
                            return False
                        content["gpio"][child.tag[5:]] = nr
                        gpios.append(nr)
                    else:
                        content[child.tag] = child.text
                result[content['name']] = content
                debug(content)                    
            return result

        debug("read_xml_config()")
        xml = ElementTree.parse(XML_FILE)
        root = xml.getroot()
        gpios = []
        try:
            for child in root.find('obswebsocket').findall('*'):
                debug(child.tag, child.text)
                self.obs[child.tag] = child.text
                # memorize gpio to warn if already in use
                if "gpio" in child.tag:
                    gpios.append(int(child.text))
        except AttributeError:
            print ("ERROR: could not find 'obswebsocket' in XMLfile '{}'".format(
                XML_FILE))
            return False
        self.scenes = _readSubTags(root, 'scene', gpios)
        self.sources = _readSubTags(root, 'source', gpios)

        if not self.scenes and not self.sources:
            print("WARNING: no scenes/sources configured!")
        return True

    def initialise_leds(self):
        """
        initialise LED objects and gpios
        """
        debug("initialise_leds()")
        if self.obs['gpio_connected']:
            self.obs['gpio_connected'] = LED(self.obs['gpio_connected'])
            self.obs['gpio_connected'].off()
        for o in (self.scenes, self.sources):
            for s in o:
                for typ in o[s]['gpio']:
                    o[s]['led'][typ] = LED(o[s]['gpio'][typ])
                    o[s]['led'][typ].off()

    def get_actual_status(self):
        """
        request actual scene/source status from OBS
        an update LEDs
        """
        debug("... get_actual_status()")
        # enable LED if source is actualy on preview
        scene = self.ws.call(requests.GetPreviewScene())
        self.on_preview(scene, scene.getName())
        # enable LED if scene is actualy on program
        scene = self.ws.call(requests.GetCurrentScene())
        self.on_switch(scene, scene.getName())

    def obs_connect(self):
        """
        initialisation ob OBS websocket
        """
        debug("obs_connect({}:{})".format(
            self.obs['host'],
            self.obs['port'],
            ))
        self.ws = obsws(self.obs['host'],
                   self.obs['port'],
                   self.obs['pass'])
        self.ws.register(self.on_heartbeat, events.Heartbeat)        
        self.ws.register(self.on_switch, events.SwitchScenes)
        self.ws.register(self.on_preview, events.PreviewSceneChanged)
        # try to get a connection to OBS
        while self.try_to_connect() != True:
            pass

    '''
    LED SWITCHING
    '''
    def _switch_led(self, typ, message, name = None):
        """
        enable/disable LEDs conforming the recived message-type
        """
        debug("... switch_led({})".format(typ))
        if not name:
            name = message.getSceneName().encode('utf-8')

        def _switch_gpio(objtyp, objects, typ, selection):
            """
            subfunction to handle all configured GPIOs
            conforming the featuare settings
            """
            on = False
            self.act_gpio[typ] = None
            for s in objects:
                if s in selection:
                    self.act_gpio[typ] = (objtyp,s)
                    print ("GPIO {:02d}: {} '{}' {}".format(
                        objects[s]['gpio'][typ],
                        "scene  " if objtyp == 'scenes' else "source ",
                        s,
                        "on" if typ == "program" else typ))
                    objects[s]['led'][typ].on()
                    on = True
                else:
                    objects[s]['led'][typ].off()
            if not self.act_gpio['preview']:
                return on
            # HINT: The enabled LEDs can be one from scenes or sources, so both mut be checkes
            prev_obj = self.scenes if self.act_gpio['preview'][0] == 'scenes' else self.sources
            if ONLY_ONE_LED_PER_CAM_ON:
                # FEATURE: Avoid showing both LEDs for one CAM
                # Each CAM can be only in program  or in preview. Showing both is
                # confusing for the person in front of the cam
                if self.act_gpio['program'] and self.act_gpio['preview']:
                    if self.act_gpio['program'] == self.act_gpio['preview']:
                        prev_obj[self.act_gpio['preview'][1]]['led']['preview'].off()
                    else:
                        prev_obj[self.act_gpio['preview'][1]]['led']['preview'].on()
                # In case "program" is unknown, that (re-)enable "preview" LED
                if not self.act_gpio['program'] and self.act_gpio['preview']:
                    prev_obj[self.act_gpio['preview'][1]]['led']['preview'].on()
            if MAX_ONE_LED_ON:
                # FEATURE: maximal one LED can be ON at time
                # in case program+preview are ON, disable preview
                if self.act_gpio['program'] and self.act_gpio['preview']:
                    prev_obj[self.act_gpio['preview'][1]]['led']['preview'].off()
            return on

        # check scenes
        on = _switch_gpio('scenes', self.scenes, typ, name)
        # check sources
        if not on and self.sources:
            new_sources = []
            for s in message.getSources():
                # consider only the visible ones...
                if s['render'] == True:
                    new_sources.append(s['name'])
            on = _switch_gpio('sources', self.sources, typ, new_sources)
        if not on:
            print ("       : '{}' on, but unknown".format(name))

    def on_switch(self, message, name = None):
        #debug("on_preview()")
        self._switch_led('program', message, name)

    def on_preview(self, message, name = None):
        #debug("on_preview()")
        self._switch_led('preview', message, name)

    '''
    Stay connected
    '''
    def on_heartbeat(self, message = None, reason=""):
        """
        memorize last hearbeat received from OBS
        """
        debug("... on_heartbeat({})".format(reason))
        self.connected = True
        self.last_heartbeat = time()

    def check_connection(self):
        """
        check actuall connection status based on last 'heartbeat'
        (this function is called asynchronusly every second)
        """
        debug("... check_connection()")
        diff = time() - self.last_heartbeat # time-diff in seconds
        # if actually not connected, try to reconnect
        if diff > 5:
            debug("... . diff = {}, connection = {}/{}".format(
                str(diff), self.ws.ws.connected, self.connected))
            self.try_to_connect()
        # recheck connection in X seconds
        Timer(2, self.check_connection, ()).start()

    def try_to_connect(self):
        """
        try to (re-)establish a socket connection to OBS
        """
        if self.obs['gpio_connected']:
            self.obs['gpio_connected'].blink()
        try:
            # check if host is reachable
            cmd = "ping -c 1 -w 1 " + self.obs['host'] + " >/dev/null 2>&1 "
            debug("... . (10s) " + cmd)
            result = 1
            # try 10s before given up...
            for _i in range(0, 20):
                result = os.system(cmd)
                if result == 0:
                    break
                sleep(.5)
            # if host reachable (online) reconnect
            if result == 0:
                debug("... . reconnect()")
                # FIXME: reconnect takes tooooo long!
                self.ws.reconnect()
                # if sucessfull reconnected, initialise LEDs
                if self.ws.ws.connected:
                    self.on_heartbeat(reason="force")
                    self.get_actual_status()
                    # advice OBS to send us a heartbeat (to monitor the connection)
                    # BUG: needs to be reenabled after reconnect
                    # BUG: if connection loss is <120s than will receive multiple events
                    self.ws.call(requests.SetHeartbeat(True))
                    # update LED to show actual status
                    if self.obs['gpio_connected']:
                        self.obs['gpio_connected'].on()
                    return True
            else:
                debug("... . ping not sucessfull, wait...")
                return False
        except Exception as e:
            debug(">>>> EXCEPTION: " + str(e))
            pass

    '''
    MAIN
    '''
    def run(self):
        """
        rund endless
        """
        # FIXME: ok for the beginning...
        debug("... run()")
        try:
            while True:
                pass
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    # execute only if run as a script
    tally = OBStally()
