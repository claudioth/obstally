#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Features:
# * real XML config, not depenting of tag ordering
# * no limitation of scene amount
# * enable LED directly on startup if scenes are shown
# * (Optional) Same CAM can not be preview and program at the same time
# * (Optional) Maximal one LED enable at the same time. Program has priority

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
import sched
from time import time
from threading import Timer


def debug(*txt):
    if DEBUG:
        print(">> {}".format(txt[0] if len(txt) == 1 else txt))


class OBStally:
    # configuration of the obswebsocket (host, port, pass)
    obs = {'host': None, 'port': None, 'pass': None, 'gpio_connected': None }
    # configuration of the OBS scenes (name, gpios, ...)
    scenes = {}
    # configuration of the OBS sources (name, gpios, ...)
    sources = {}
    # the websocket
    ws = None

    # CACHE: Last activated LED for a the spefic types
    act_gpio = { 'program': None, 'preview': None }
    # CACHE: actual connection status
    connected = False
    # CACHE: timestamp of last heartbeat (seconds, float)
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
        self.get_actual_status()
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
        self.ws.connect()
        if self.obs['gpio_connected']:
            self.obs['gpio_connected'].on()
        self.connected = True
        self.last_heartbeat = time()
        self.ws.call(requests.SetHeartbeat(True))
    
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
    def on_heartbeat(self, message):
        """
        memorize last hearbeat received from OBS
        """
        debug("... on_heartbeat({})")
        self.last_heartbeat = time()

    def check_connection(self):
        """
        check actuall connection status based on last 'heartbeat'
        (this function is called asynchronusly every second)
        """
        debug("... check_connection()")
        diff = time() - self.last_heartbeat # time-diff in seconds
        # if actually not connected, try to reconnect
        if diff > 2:
            self.connected = False # force LED re-init
            if self.obs['gpio_connected']:
                self.obs['gpio_connected'].blink()
            self.ws.reconnect()
        # if sucessfull reconnected, initialise LEDs again
        connected = self.ws.ws.connected
        if connected and not self.connected:
            self.connected = True
            self.get_actual_status()
        # update LED to show actual status
        if self.obs['gpio_connected']:
            if connected:
                self.obs['gpio_connected'].on()
            else:
                self.obs['gpio_connected'].off()
        # recheck connection in X seconds
        Timer(1, self.check_connection, ()).start()

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
