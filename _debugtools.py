#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__      = "Claudio Thomas"
__copyright__   = "Copyright 2020"
__license__     = "GPL"

from _contants import DEBUG

def debug(*txt):
    if DEBUG:
        print(">> {}".format(txt[0] if len(txt) == 1 else txt))
