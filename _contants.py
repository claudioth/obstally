#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os.path import abspath, dirname


DEBUG = True  # additional debugging output

XML_FILE = "{}/obstally.xml".format(dirname(abspath(__file__)))

# Features
ONLY_ONE_LED_PER_CAM_ON = True  # Same CAM can not be preview and program at the same time
MAX_ONE_LED_ON = True  # maximal one LED enabled at the same time, program LED has priority
