#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Features:
# * real XML config, not depenting of tag ordering
# * no limitation of scene amount
# * enable LED directly on startup if scenes are shown

DEBUG = True
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
        print(txt[0] if len(txt) == 1 else txt)


class OBStally:
    # configuration of the obswebsocket (host, port, pass)
    obs = {}
    # configuration of the OBS scenes (name, gpios, ...)
    scenes = {}
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
        for s in root.findall('scene'):
            scene = {}
            for child in s.findall('*'):
                debug(child.tag, child.text)
                scene[child.tag] = child.text
                if "gpio" in child.tag:
                    if int(child.text) in gpios:
                        print("ERROR: GPIO {} can only be used once!".format(
                            child.text))
                        return False
                    gpios.append(int(child.text))
            self.scenes[scene['name']] = scene
        if not self.scenes:
            print("WARNING: no scenes configured!")
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
        # enable LED if scene is actualy on preview
        scene = self.ws.call(requests.GetPreviewScene())
        if scene.datain and scene.datain['name'] in self.scenes:
            self.scenes[scene.datain['name']]['led_preview'].on()
        # enable LED if scene is actualy on program
        scene = self.ws.call(requests.GetCurrentScene())
        if scene.datain and scene.datain['name'] in self.scenes:
            self.scenes[scene.datain['name']]['led_program'].on()

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
    
    def on_switch(self, message):
        name = message.getSceneName()
        for s in self.scenes:
            if s == name:
                print ("GPIO {:02d}: '{}' on".format(
                    int(self.scenes[s]['gpio_program']), s))
                self.scenes[s]['led_program'].on()
            else:
                self.scenes[s]['led_program'].off()
        if not self.scenes[s]:
            print ("{} on, but unknown".format(s))

    def on_preview(self, message):
        name = message.getSceneName()
        for s in self.scenes:
            if s == name:
                print ("GPIO {:02d}: '{}' preview".format(
                    int(self.scenes[s]['gpio_preview']), s))
                self.scenes[s]['led_preview'].on()
            else:
                self.scenes[s]['led_preview'].off()
        if not self.scenes[s]:
            print ("{} preview, but unknown".format(s))

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
