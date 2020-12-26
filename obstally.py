#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Features:
# * real XML config, not depenting of tag ordering
# * no limitation of scene amount
# * enable LED directly on startup if scenes are shown
# * (Optional) Same CAM can not be preview and program at the same time

DEBUG = True  # additional debugging output
ONLY_ONE_LED_PER_CAM_ON = True

# Please define here the name of your XMLS config file
# (by default it is saved on the save path as the executable)
from os.path import abspath, dirname
XML_FILE = "{}/obstally.xml".format(dirname(abspath(__file__)))


from gpiozero import LED
from obswebsocket import obsws, events, requests
from xml.etree import ElementTree
from RPi import GPIO


def debug(*txt):
    if DEBUG:
        print(">> {}".format(txt[0] if len(txt) == 1 else txt))


class OBStally:
    # configuration of the obswebsocket (host, port, pass)
    obs = {}
    # configuration of the OBS scenes (name, gpios, ...)
    scenes = {}
    # configuration of the OBS sources (name, gpios, ...)
    sources = {}
    # the websocket
    ws = None

    # CACHE: Last activated LED for a the spefic types
    act_gpio = { 'program': None, 'preview': None }
    
    '''
    INITIALISATION
    '''
    def __init__(self):
        """
        initialise the enviroment
        """
        debug("__init__()")
        # basic python environment initialisation
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.cleanup()
        # read xml an init leds based on config
        if not self.read_xml_config():
            return
        self.obs_connect()
        self.initialise_leds()
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
        for o in (self.scenes, self.sources):
            for s in o:
                for typ in o[s]['gpio']:
                    o[s]['led'][typ] = LED(o[s]['gpio'][typ])
                    o[s]['led'][typ].off()
        # enable LED if source is actualy on preview
        scene = self.ws.call(requests.GetPreviewScene())
        self.on_preview(scene, scene.datain['name'])
        # enable LED if scene is actualy on program
        scene = self.ws.call(requests.GetCurrentScene())
        self.on_switch(scene, scene.datain['name'])

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
        self.ws.register(self.on_switch, events.SwitchScenes)
        self.ws.register(self.on_preview, events.PreviewSceneChanged)
        self.ws.connect()
    
    '''
    LED SWITCHING
    '''
    def _switch_led(self, typ, message, name = None):
        debug("... switch_led({})".format(typ))
        if not name:
            name = message.getSceneName().encode('utf-8')

        def _switch_gpio(objects, typ, selection):
            on = False
            self.act_gpio[typ] = ""
            for s in objects:
                if s == selection:
                    self.act_gpio[typ] = s
                    print ("GPIO {:02d}: '{}' {}".format(
                        objects[s]['gpio'][typ],
                        s,
                        "on" if typ == "program" else typ))
                    objects[s]['led'][typ].on()
                    on = True
                else:
                    objects[s]['led'][typ].off()
            # only on "program" disable "preview" LED if its the same CAM
            if ONLY_ONE_LED_PER_CAM_ON:
                if self.act_gpio['program'] and self.act_gpio['preview']:
                    print(typ, self.act_gpio['program'], self.act_gpio['preview'])
                    if self.act_gpio['program'] == self.act_gpio['preview']:
                        objects[self.act_gpio['preview']]['led']['preview'].off()
                    else:
                        objects[self.act_gpio['preview']]['led']['preview'].on()
                # In case "program" is unknown, that (re-)enable "preview" LED
                if not self.act_gpio['program'] and self.act_gpio['preview']:
                    objects[self.act_gpio['preview']]['led']['preview'].on()
            return on

        # check scenes
        on = _switch_gpio(self.scenes, typ, name)
        # check sources
        if not on and self.sources:
            new_sources = []
            for s in message.getSources():
                # consider only the visible ones...
                if s['render'] == True:
                    new_sources.append(s['name'])
            on = _switch_gpio(self.sources, typ, new_sources)
        if not on:
            print ("       : '{}' on, but unknown".format(name))

    def on_switch(self, message, name = None):
        #debug("on_preview()")
        self._switch_led('program', message, name)

    def on_preview(self, message, name = None):
        #debug("on_preview()")
        self._switch_led('preview', message, name)

    def run(self):
        """
        rund endless
        """
        # FIXME: ok for the beginning...
        debug("run()")
        try:
            while True:
                pass
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    # execute only if run as a script
    tally = OBStally()
