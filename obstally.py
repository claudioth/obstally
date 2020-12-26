#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Features:
# * real XML config, not depenting of tag ordering
# * no limitation of scene amount

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
        self.read_xml_config()
        self.initialise_leds()
        self.obs_connect()
        
    def read_xml_config(self):
        """
        read the configuration from the XML-file and save the values
        to the dictionaries
        """
        debug("read_xml_config()")
        xml = ElementTree.parse(XML_FILE)
        root = xml.getroot()
        try:
            for child in root.find('obswebsocket').findall('*'):
                debug(child.tag, child.text)
                self.obs[child.tag] = child.text
        except AttributeError:
            print ("ERROR: could not find 'obswebsocket' in XMLfile '{}'".format(
                XML_FILE))
            return
        for s in root.findall('scene'):
            scene = {}
            for child in s.findall('*'):
                debug(child.tag, child.text)
                scene[child.tag] = child.text
            self.scenes[scene['name']] = scene
        if not self.scenes:
            print("WARNING: no scenes configured!")

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

    def obs_connect(self):
        """
        initialisation ob OBS websocket 
        """
        debug("obs_connect({}:{})".format(
            self.obs['host'],
            self.obs['port'],
            ))
        ws = obsws(self.obs['host'],
                   self.obs['port'],
                   self.obs['pass'])
        ws.connect()
    

if __name__ == "__main__":
    # execute only if run as a script
    tally = OBStally()
