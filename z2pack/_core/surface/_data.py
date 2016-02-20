#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author:  Dominik Gresch <greschd@gmx.ch>
# Date:    08.02.2016 16:04:23 CET
# File:    _data.py

import six
from ptools.locker import Locker
from sortedcontainers import SortedList

class SurfaceData(metaclass=Locker):
    def __init__(self):
        self.lines = SortedList(key=lambda x: x.t)

    def add(self, t, line_result):
        self.lines.add(SurfaceLine(t, line_result))

    @property
    def t(self):
        return tuple(line.t for line in self.lines)

    def nearest_neighbour_dist(self, t):
        return min(abs(t - tval) for tval in self.t)

class SurfaceLine(metaclass=Locker):
    def __init__(self, t, line_data):
        self.t = t
        self.line_result = line_result