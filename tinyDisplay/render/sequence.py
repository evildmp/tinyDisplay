# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Sequence enables a series of canvases to be displayed

.. versionadded:: 0.0.1
"""
import time
import bisect
import logging
from operator import itemgetter
from PIL import Image
from tinyDisplay.utility import dataset as Dataset
from tinyDisplay.render.widget import image, canvas


class collection():

    def __init__(self, name=None, size=(0, 0), sequences=None, defaultCanvas=None):
        self._sequences = sequences if sequences else []
        self.size = size

        if not defaultCanvas:
            defaultCanvas = image(image=Image.new('1', size))  # Set an empty image if no defaultCanvas provided
        self._defaultCanvas = defaultCanvas

        self._priorities = []
        if sequences:
            # Sort from lowest to highest priority
            self._sequences.sort(key=itemgetter(0)._priority)
            self._priorites = [s[0]._priority for s in self._sequences]

        self._minTimer = {}
        self._inUse = set()
        self._cooling = {}

    def append(self, sequence=None, placement=None, just=None):
        placement = placement if placement else (0, 0)
        just = just if just else 'lt'

        pos = bisect.bisect_left(self._priorities, sequence._priority)
        self._priorities.insert(pos, sequence._priority)
        self._sequences.insert(pos, (sequence, placement, just))

    def render(self, force=False):

        ct = time.time()

        # minDuration and cooling values are (startTime, duration)
        # a sequence that is cooling cannot be activated

        # Remove any sequence that's cooling period has ended
        self._cooling = {k: v for k, v in self._cooling.items() if v[0] + v[1] >= ct}

        # Remove any sequence that's minDuration period has ended
        self._minTimer = {k: v for k, v in self._minTimer.items() if v[0] + v[1] >= ct}

        renderList = []
        # Look for active sequences from highest priority to lowest
        for s, pl, j in reversed(self._sequences):
            m = s._minDuration
            c = s._coolingPeriod

            if (s.active and s not in self._cooling) or s in self._minTimer:
                # If sequence is newly activated, force render it and place it in the inUse record.
                # Also record start time in _active and _cooling
                inUse = False
                if s not in self._inUse:
                    self._inUse.add(s)
                    self._minTimer[s] = (ct, m)
                    self._cooling[s] = (ct, c)
                    inUse = True
                renderList.append((s, s.render(inUse)[0], pl, j))
            else:
                if s in self._inUse:
                    self._inUse.remove(s)

        if not self._inUse:
            renderList.append((self._defaultCanvas, self._defaultCanvas.render(True)[0], (0, 0), 'lt'))

        c = canvas(size=self.size)
        for s, img, pl, j in renderList:
            c.append(widget=image(img), placement=pl, anchor=j)

        return c.render()


class sequence():
    def __init__(self, name=None, condition='False', minDuration=0, priority=logging.INFO, coolingPeriod=0, dataset=None, canvases=None, defaultCanvas=None):
        """
        Create a new sequence instance

        :param name: the name of the new sequence
        :type name: str
        :param condition: boolean function to determine if the sequence is active based the information contained within the dataset.  Can either be a function or a string that 'evals' to a boolean
        :type condition: function or str
        :param dataset: shared dataset for all widgets, canvases, and sequences
        :type dataset: dict
        :param defaultCanvas: returned by render when there is no active canvas
        :type defaultCanvas: tinyDisplay.utility.widget
        """
        self.name = name
        self._priority = priority if priority else logging.info
        self._minDuration = minDuration if minDuration else 0
        self._coolingPeriod = coolingPeriod if coolingPeriod else 0
        self._dataset = Dataset(dataset) if dataset and type(dataset) is dict else dataset if dataset else Dataset()
        self._condition = self._dataset.compile(condition) if type(condition) is str else condition

        if not defaultCanvas:
            defaultCanvas = image(image=Image.new('1', (0, 0)))  # Set an empty image if no defaultCanvas provided
        self._defaultCanvas = defaultCanvas

        self.size = max((0, 0), self._defaultCanvas.size)
        self._canvases = []
        self._currentCanvas = None

        # Populate canvases if provided
        if canvases:
            for c in canvases:
                # Canvas tuple is (canvas, duration, minDuration, condition)
                # Min information that can be provided is (canvas, duration)
                if len(c) < 2:
                    raise ValueError('Each canvas in a sequence must provide at least a duration')
                if len(c) == 2:
                    # if only (canvas, duration) provided, add minDuration of 0 and a condition of True
                    c = (c[0], c[1], 0, 'True')
                self.append(*c)

        self.reset()  # Initialize starting time to now

    def __repr__(self):
        n = self.name if self.name else 'unnamed'

        return f'<sequence {n} at 0x{id(self):x}>'

    def append(self, canvas, duration=1, minDuration=0, condition='True'):
        """
        Add a canvas to the sequence

        :param canvas: the canvas to be added to the sequence
        :type canvas: tinyDisplay.Canvas
        :param duration: the set of canvas images needed to render the current set of sequences
        :type duration: float
        :param minDuration: the minimum amount of time this canvas should remain active (even if condition becomes False)
        :param condition: boolean function to determine if the canvas is active based the information contained within the dataset.  Can either be a function or a string that 'evals' to a boolean
        :type condition: function or str
        """
        duration = duration if duration else 1
        minDuration = minDuration if minDuration else 0
        condition = condition if condition else 'True'

        condition = self._dataset.compile(condition) if type(condition) is str else condition
        self._canvases.append((canvas, duration, minDuration, condition))
        canvas.render(True)
        cs = canvas.size
        mx = max(cs[0], self.size[0])
        my = max(cs[1], self.size[1])
        self.size = (mx, my)

    def render(self, force=False):
        if force:
            self.reset()

        c, new = self.activeCanvas()
        if not c:
            return self._defaultCanvas.render()
        return c.render(new)

    def stop(self):
        for c in self._canvases:
            c[0].stop()

    def activeCanvas(self):
        """
        Determine and return the current canvas.

        :return: the currently active Canvas or None if no canvas is active and whether the activeCanvas is newly activated
        :rtype: (tinyDisplay.render.widget, bool)

        """
        flag = False
        cc = self._currentCanvas

        # Iterate through list of canvases to see which one should be active
        # list iterates one past the length of canvas list in case the current canvas has expired but should remain active
        # because it is the only active canvas
        for i in range(len(self._canvases) + 1):

            # If the canvas remains active and has not expired OR
            # the canvas still has some minimum time remaining
            if self._activeCanvas() and not self._expiredCurrentCanvas():

                # If canvas expired but winds up as the next active canvas anyway
                # then do not indicate that it is new
                flag = False if cc == self._currentCanvas else flag

                return (self._canvases[self._currentCanvas][0], flag)
            flag = True
            self._reset()
            self._currentCanvas += 1
            if self._currentCanvas == len(self._canvases):
                self._currentCanvas = 0

        return (None, False)

    @property
    def active(self):
        """
        Report whether the sequence is active or not

        :return: boolean indicating whether the sequence is active
        :rtype: bool
        """
        return self._dataset.eval(self._condition)

    def reset(self):
        """
        Reset sequence to the beginning
        """
        self._currentCanvas = 0
        self._reset()

    def _activeCanvas(self):
        return (self._dataset.eval(self._canvases[self._currentCanvas][3]) or self._timeRemainingCurrentCanvas())

    def _reset(self):
        """
        Reset canvas timer
        """

        self.start = time.time()

    def _expiredCurrentCanvas(self):
        """
        Determine whether the current Canvas's time is expired

        :return: True if time has expired otherwise False
        :rtype: bool
        """

        if time.time() - self.start > self._canvases[self._currentCanvas][1]:
            return True
        return False

    def _timeRemainingCurrentCanvas(self):
        """
        Determine whether the current Canvas has time remaining (minimum time has not expired)

        :return: True if minimum time has not expired else False
        :rtype: bool
        """

        if time.time() - self.start > self._canvases[self._currentCanvas][2]:
            return False
        return True

    def timeRemaining(self):
        """
        Determine whether the sequence has time remaining (minimum time has not expired)

        :return: True if minimum time has not expired else False
        :rtype: bool
        """

        if time.time() - self.start > self._minDuration:
            return False
        return True
