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


from xml.etree import ElementTree 

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
        # read xml an init leds based on config
        self.read_xml_config()
        
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

if __name__ == "__main__":
    # execute only if run as a script
    tally = OBStally()
