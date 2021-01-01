#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OBS Tallylights via OBS-Websockets and GPIOzero.

This Toolset was written to support sundays-church-streaming
"""
__author__      = "Claudio Thomas"
__copyright__   = "Copyright 2020"
__license__     = "GPL"

# standard
# third party
from gpiozero import LED
from obswebsocket import events, requests
# own
from wsclient import wsclient
from _contants import ONLY_ONE_LED_PER_CAM_ON, MAX_ONE_LED_ON
from _debugtools import debug


class tally(wsclient):
    ''' configuration attributes '''
    # known OBS scenes (name, gpios, ...)
    scenes = {}
    # known OBS sources (name, gpios, ...)
    sources = {}

    ''' runtime changebled/status attributes '''
    # last activated LED for a the spefic type
    act_gpio = { 'program': None, 'preview': None }

    def read_xml_config(self):
        """
        read the configuration from the XML-file and save the values
        to the dictionaries
        """
        if not super(tally, self).read_xml_config():
            return False
        debug("tally.read_xml_config()")
        self.scenes = self._readSubTags(self.rootxml, 'scene')
        self.sources = self._readSubTags(self.rootxml, 'source')

        if not self.scenes and not self.sources:
            print("WARNING: no scenes/sources configured!")
        return True

    def initialise_leds(self):
        """
        initialise LED objects and gpios
        """
        super(tally, self).initialise_leds()
        debug("tally.initialise_leds()")
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

    def register_obs_events(self):
        """
        register request to be receivesd from OBS
        """
        super(tally, self).register_obs_events()
        debug("tally.register_obs_events()")
        self.ws.register(self.on_switch, events.SwitchScenes)
        self.ws.register(self.on_preview, events.PreviewSceneChanged)


    '''
    LED SWITCHING
    '''
    def _all_leds_off(self, typ):
        """
        switch all LEDs off
        """
        for o in (self.scenes, self.sources):
            for s in o:
                for typ in o[s]['gpio']:
                    o[s]['led'][typ].off()

    def _all_leds_on(self, typ):
        """
        switch all LEDs off
        """
        for o in (self.scenes, self.sources):
            for s in o:
                for typ in o[s]['gpio']:
                    o[s]['led'][typ].on()

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

    def on_disconnect(self):
        """
        perform actions when connection is lost
        """
        super(tally, self).on_disconnect()
        # all LEDs ON
        self._all_leds_on('program')
        self._all_leds_on('preview')

    def on_switch(self, message, name = None):
        #debug("on_preview()")
        self._switch_led('program', message, name)

    def on_preview(self, message, name = None):
        #debug("on_preview()")
        self._switch_led('preview', message, name)

    '''
    MAIN
    '''
    def run(self):
        """
        rund endless
        """
        # FIXME: ok for the beginning...
        debug("... tally.run()")
        try:
            while True:
                pass
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    # execute only if run as a script
    test_obj = tally()
