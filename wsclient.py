#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Base Class
"""
__author__      = "Claudio Thomas"
__copyright__   = "Copyright 2020"
__license__     = "GPL"

# standard
from os import system
from time import time, sleep
from threading import Timer
from xml.etree import ElementTree
# third party
from gpiozero import LED
from obswebsocket import obsws, events, requests
# own
from _contants import XML_FILE
from _debugtools import debug


class wsclient(object):
    ''' configuration attributes '''
    # the obswebsocket (host, port, pass)
    obs = {'host': None, 'port': None, 'pass': None, 'gpio_connected': None }
    # th gpios in use
    gpios = []
    
    ''' runtime changebled/status attributes '''
    # actual connection status
    connected = False
    # timestamp in secons of last heartbeat (float)
    last_heartbeat = None
    # the root-xml tree
    rootxml = None
    # the websocket object
    ws = None

    '''
    INITIALISATION and HELPER functions
    '''
    def __init__(self):
        """
        initialise the enviroment
        """
        debug("wsclient.__init__()")
        # read xml an init leds based on config
        if not self.read_xml_config():
            return
        # OBS websocket initialisation
        self.initialise_leds()
        self.connection_start()
        # prepare schedular to monitor connection
        Timer(1, self.connection_check, ()).start()
        # run endless
        self.run()

    def _readSubTags(self, root, tag):
        """
        internal helper function to read all tags of a xml-branch
        """
        result = {}
        for s in root.findall(tag):
            content = {'name': "", "gpio": {}, 'led': {} }
            for child in s.findall('*'):
                if "gpio" in child.tag:
                    nr = int(child.text)
                    if nr in self.gpios:
                        print("ERROR: GPIO {} can only be used once!".format(nr))
                        return False
                    content["gpio"][child.tag[5:]] = nr
                    self.gpios.append(nr)
                else:
                    content[child.tag] = child.text
            result[content['name']] = content
            debug(content)                    
        return result

    def run(self):
        """
        rund endless
        """
        # FIXME: ok for the beginning...
        debug("... wsclient.run()")
        try:
            while True:
                pass
        except KeyboardInterrupt:
            pass

    '''
    OBS CONNECTION
    '''
    def connection_check(self):
        """
        check actuall connection status based on last 'heartbeat'
        (this function is called asynchronusly every second)
        """
        debug("... " + "wsclient.connection_check()")
        diff = time() - self.last_heartbeat # time-diff in seconds
        # if actually not connected, try to reconnect
        if diff > 5:
            debug("... . diff = {}, connection = {}/{}".format(
                str(diff), self.ws.ws.connected, self.connected))
            self.connection_try()
        # recheck connection in X seconds
        Timer(2, self.connection_check, ()).start()

    def connection_start(self):
        """
        initialisation ob OBS websocket
        """
        debug("wsclient.connection_start({}:{})".format(
            self.obs['host'],
            self.obs['port'],
            ))
        self.ws = obsws(self.obs['host'],
                   self.obs['port'],
                   self.obs['pass'])
        self.register_obs_events()
        # try to get a connection to OBS
        while self.connection_try() != True:
            pass

    def connection_try(self):
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
                result = system(cmd)
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

    def on_heartbeat(self, message = None, reason=""):
        """
        memorize last hearbeat received from OBS
        """
        debug("... " + "wsclient.on_heartbeat({})".format(reason))
        self.connected = True
        self.last_heartbeat = time()

    """
    FUNCTIONS to be extended/overwritten on inheritance
    """
    def get_actual_status(self):
        """
        request actual status data from OBS
        
        (placeholder, to be overloaded from inherited classes)
        """
        pass

    def initialise_leds(self):
        """
        initialise LED objects and gpios
        
        Can be extended by inherited classes:
           super(XXX, self).initialise_leds()
        """
        debug("wsclient.initialise_leds()")
        if self.obs['gpio_connected']:
            self.obs['gpio_connected'] = LED(self.obs['gpio_connected'])
            self.obs['gpio_connected'].off()

    def read_xml_config(self):
        """
        read the configuration from the XML-file and save the values
        to the dictionaries
        
        Can be extended by inherited classes:
           if not super(XXX, self).read_xml_config():
            return False         
        """
        debug("wsclient.read_xml_config()")
        xml = ElementTree.parse(XML_FILE)
        self.rootxml = xml.getroot()
        try:
            for child in self.rootxml.find('obswebsocket').findall('*'):
                debug(child.tag, child.text)
                self.obs[child.tag] = child.text
                # memorize gpio to warn if already in use
                if "gpio" in child.tag:
                    self.gpios.append(int(child.text))
        except AttributeError:
            print ("ERROR: could not find 'obswebsocket' in XMLfile '{}'".format(
                XML_FILE))
            return False
        return True

    def register_obs_events(self):
        """
        register request to be receivesd from OBS
        
        Can be extended by inherited classes:
           super(XXX, self).register_obs_events()
        """
        debug("wsclient.register_obs_events()")
        self.ws.register(self.on_heartbeat, events.Heartbeat)        
        

if __name__ == "__main__":
    # execute only if run as a script
    test_obj = wsclient()
