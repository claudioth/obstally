#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Features:
# * real XML config, not depenting of tag ordering
# * no limitation of scene amount
# * enable LED directly on startup if scenes are shown

DEBUG = True  # additional debugging output
PRGFIRST = True  # IF scene is in preview+program, only program LED is on

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
                content = {}
                for child in s.findall('*'):
                    debug(child.tag, child.text)
                    if "gpio" in child.tag:
                        nr = int(child.text)
                        if nr in gpios:
                            print("ERROR: GPIO {} can only be used once!".format(nr))
                            return False
                        content[child.tag] = nr
                        gpios.append(nr)
                    else:
                        content[child.tag] = child.text
                result[content['name']] = content
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
        for s in self.scenes:
            self.scenes[s]['led_program'] = LED(self.scenes[s]['gpio_program'])
            self.scenes[s]['led_program'].off()
            self.scenes[s]['led_preview'] = LED(self.scenes[s]['gpio_preview'])
            self.scenes[s]['led_preview'].off()

        for s in self.sources:
            self.sources[s]['led_program'] = LED(self.sources[s]['gpio_program'])
            self.sources[s]['led_program'].off()
            self.sources[s]['led_preview'] = LED(self.sources[s]['gpio_preview'])
            self.sources[s]['led_preview'].off()
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
    
    def on_switch(self, message, name = None):
        if not name:
            name = message.getSceneName().encode('utf-8')
        on = False
        # check scenes
        for s in self.scenes:
            if s == name:
                print ("GPIO {:02d}: '{}' on".format(
                    int(self.scenes[s]['gpio_program']), s))
                self.scenes[s]['led_program'].on()
                on = True
            else:
                self.scenes[s]['led_program'].off()
        # check sources
        if not on and self.sources:
            new_sources = []
            for s in message.getSources():
                if s['render'] == True:
                    new_sources.append(s['name'])
            for s in self.sources:
                if s in new_sources:
                    print ("GPIO {:02d}: '{}' on (source)".format(
                        int(self.sources[s]['gpio_program']), s))
                    self.sources[s]['led_program'].on()
                    on = True
                else:
                    self.sources[s]['led_program'].off()
        if not on:
            print ("       : '{}' on, but unknown".format(name))

    def on_preview(self, message, name = None):
        if not name:
            name = message.getSceneName().encode('utf-8')
        on = False
        # check scenes
        for s in self.scenes:
            if s == name:
                print ("GPIO {:02d}: '{}' preview".format(
                    int(self.scenes[s]['gpio_preview']), s))
                self.scenes[s]['led_preview'].on()
                on = True
            else:
                self.scenes[s]['led_preview'].off()
        # check sources
        if not on and self.sources:
            new_sources = []
            for s in message.getSources():
                if s['render'] == True:
                    new_sources.append(s['name'])
            for s in self.sources:
                if s in new_sources:
                    print ("GPIO {:02d}: '{}' preview (source)".format(
                        int(self.sources[s]['gpio_preview']), s))
                    self.sources[s]['led_preview'].on()
                    on = True
                else:
                    self.sources[s]['led_preview'].off()
        if not on:
            print ("       : '{}' preview, but unknown".format(name))

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
