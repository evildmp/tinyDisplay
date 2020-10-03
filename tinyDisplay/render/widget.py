# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Widgets for the tinyDisplay system

.. versionadded:: 0.0.1
"""
import pathlib
import abc

from PIL import Image, ImageDraw
from tinyDisplay.utility import dataset as Dataset
from tinyDisplay.font import tdImageFont


class widget(metaclass=abc.ABCMeta):

    def __init__(self, name=None, size=None, dataset=None, just='lt'):
        """
        Create a new widget

        :param size: the max size of the widget (x,y)
        :type size: tuple
        :param dataset: shared dataset for all widgets, canvases, and sequences
        :type dataset: dict
        """
        self.name = name
        self._requestedSize = size
        self._dataset = Dataset(dataset)
        self.just = just.lower()
        self.type = self.__class__.__name__
        self.image = None
        self.current = None
        self._reprVal = None

        self._computeLocalDB()

    def _computeLocalDB(self):
        self._localDB = {'widget':
            {
                'size': self.size,
                'name': self.name,
                'just': self.just,
            }
        }

    @property
    def size(self):
        if self.image:
            return self.image.size
        if self._requestedSize:
            return self._requestedSize
        return (0, 0)

    def __repr__(self):
        cw = ''
        n = self.name if self.name else 'unnamed'
        v = f'value({self._reprVal}) ' if self._reprVal else ''
        return f'<{n}.{self.type} {v}size{self.size} {cw}at 0x{id(self):x}>'

    def clear(self):
        """
        Set the image of the widget to empty and the default size of the widget
        """
        self.image = Image.new("1", self.size)

    def _eval(self, v):
        return self._dataset.eval(v, dataset=self._localDB)

    def _compile(self, stmt):
        try:
            return self._dataset.compile(stmt, self._localDB) if type(stmt) == str else stmt
        except (NameError, SyntaxError):
            return stmt

    def _place(self, retainImage=False, wImage=None, offset=(0, 0), just='lt'):
        just = just or 'lt'
        offset = offset or (0, 0)
        assert wImage, 'Cannot place widget.  No widget provided'
        assert just[0] in 'lmr' and just[1] in 'tmb', \
            f'Requested justification "{just}" is invalid.  Valid values are left top (\'lt\'), left middle (\'lm\'), left bottom (\'lb\'), middle top (\'mt\'), middle middle (\'mm\'), middle bottom (\'mb\'), right top (\'rt\'), right middle (\'rm\'), and right bottom (\'rb\')'

        # Reset image if thie is not a multi-placement (e.g. canvas)
        if not retainImage:
            self.image = None

        # If no existing image and no size requested then the provide wImage is the image
        if not self.image and not self._requestedSize:
            self.image = wImage
            return (0, 0)

        # If no existing image and a size has been requested, provision a new image
        if not self.image:
            self.image = Image.new('1', self._requestedSize)

        # If a size has been requested, crop the image to the requested size
        # Note: Not sure I need this, not executing during testing
        if self._requestedSize:
            if self.image.size != self._requestedSize:
                self.image = self.image.crop((0, 0, self._requestedSize[0], self._requestedSize[1]))

        mh = round((self.image.size[0] - wImage.size[0]) / 2)
        r = self.image.size[0] - wImage.size[0]

        mv = round((self.image.size[1] - wImage.size[1]) / 2)
        b = self.image.size[1] - wImage.size[1]

        a = \
            0 if just[0] == 'l' else \
            mh if just[0] == 'm' else \
            r if just[0] == 'r' else \
            0
        b = \
            0 if just[1] == 't' else \
            mv if just[1] == 'm' else \
            b if just[1] == 'b' else \
            0

        pos = (offset[0] + a, offset[1] + b)
        self.image.paste(wImage, pos)
        return (pos[0], pos[1])

    def render(self, *args, **kwargs):
        self._computeLocalDB()
        img, changed = self._render(*args, **kwargs)
        return (img, changed)

    @abc.abstractmethod
    def _render(self, *args, **kwargs):
        """
        Compute image for widget based upon its configuration and the current dataset values

        :param force: Set force True to force the widget to re-render itself
        :type force: bool
        :param tick: Change the current tick (e.g. time) for animated widgets
        :type tick: int
        :param move: Determine whether time moves forward during the render. Default is True.
        :type move: bool
        :return: a 2-tuple with the widget's current image and a flag to indicate whether
            the image has just changed.  If force was set, it will always return changed
        :rtype: (PIL.Image, bool)
        """
        pass    # pragma: no cover


_textDefaultFont = tdImageFont(pathlib.Path(__file__).parent / "../fonts/hd44780.fnt")


class text(widget):

    def __init__(self, value=None, font=None, lineSpacing=0, *args, **kwargs):
        super().__init__(*args, **kwargs)

        font = font or _textDefaultFont
        self.font = font
        self.lineSpacing = lineSpacing
        self._cValue = self._compile(value)
        self._tsDraw = ImageDraw.Draw(Image.new('1', (0, 0)))

        self.render(force=True)

    def _render(self, force=False, *args, **kwargs):
        value = str(self._eval(self._cValue))

        # If the string to render has not changed then return current image
        if value == self.current and not force:
            return (self.image, False)
        self.current = value
        self._reprVal = f"'{value}'"

        tSize = self._tsDraw.textsize(value, font=self.font, spacing=self.lineSpacing)
        tSize = (0, 0) if tSize[0] == 0 else tSize

        img = Image.new('1', tSize)
        if img.size[0] != 0:
            d = ImageDraw.Draw(img)
            just = {'l': 'left', 'r': 'right', 'm': 'center'}.get(self.just[0])
            d.text((0, 0), value, font=self.font, fill='white', spacing=self.lineSpacing, align=just)

        self._place(wImage=img, just=self.just)
        return (self.image, True)


class staticText(text):
    def _compile(self, value):
        return value

    def _eval(self, value):
        return value


class progressBar(widget):

    def __init__(self, value=None, range=None, mask=None, barSize=None, direction='ltr',  *args, **kwargs):
        super().__init__(*args, **kwargs)

        assert mask or barSize or self._requestedSize, 'You must either provide a mask image or provide a size for the progressBar'
        assert not (mask and barSize), 'You can either provide a mask image or a barSize but not both'
        self.mask = mask if mask else self._defaultMask(barSize if barSize else self._requestedSize)
        if type(mask) in [str, pathlib.PosixPath]:
            self.mask = Image.open(pathlib.PosixPath(mask))
        self.direction = direction.lower()

        range = range if range else (0, 100)
        self._cRange = (self._compile(range[0]), self._compile(range[1]))
        self._cValue = self._compile(value)

    @staticmethod
    def _defaultMask(size):
        img = Image.new('RGB', size)
        d = ImageDraw.Draw(img)
        if size[0] - 1 < 3 or size[1] - 1 < 3:
            d.rectangle((0, 0, size[0] - 1, size[1] - 1), fill='black', outline='black')
        else:
            d.rectangle((0, 0, size[0] - 1, size[1] - 1), fill='black', outline='white')
        imga = img.copy().convert('L')
        img.putalpha(imga)
        img.load()
        return img

    @staticmethod
    def _getScaler(scale, range):

        # Convert scale and range if needed
        scale = float(scale) if type(scale) in [str, int] else scale
        r0 = float(range[0]) if type(range[0]) in [str, int] else range[0]
        r1 = float(range[1]) if type(range[1]) in [str, int] else range[1]

        if scale < r0 or scale > r1:
            scale = r0 if scale < r0 else r1

        rangeSize = r1 - r0
        return (scale - r0) / rangeSize

    def _render(self, force=False, *args, **kwargs):
        value = self._eval(self._cValue)
        range = (self._eval(self._cRange[0]), self._eval(self._cRange[1]))
        scale = self._getScaler(value, range)

        if scale == self.current and not force:
            return (self.image, False)
        self.current = scale

        self._reprVal = f'{scale*100:.1f}%'

        size = self.mask.size
        dir = self.direction

        (w, h) = (size[0], round(size[1] * scale)) if dir in ['ttb', 'btt'] else (round(size[0] * scale), size[1])
        (px, py) = (0, 0) if dir in ['ltr', 'ttb'] else (size[0] - w, 0) if dir == 'rtl' else (0, size[1] - h)

        # Build Fill
        img = Image.new('1', size)
        img.paste(Image.new('1', (w, h), 1), (px, py))
        img.paste(self.mask, (0, 0), self.mask)

        self._place(wImage=img, just=self.just)
        return (self.image, True)


class canvas(widget):
    def __init__(self, placements=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._newWidget = True
        self.placements = list(placements or [])
        self._reprVal = f'{len(self.placements) or "no"} widgets'

    def append(self, widget=None, offset=(0, 0), anchor='lt'):
        assert widget, 'Attempted to append to canvas but did not provide a widget'
        self.placements.append((widget, offset, anchor))
        self._newWidget = True

    def _render(self, force=False, *args, **kwargs):
        changed = False if not force and not self._newWidget and self.image else True

        # Render all of the widgets on the canvas
        list = []

        for i in self.placements:
            wid, off, anc = self._getPlacement(i)
            img, updated = wid.render(force=force, *args, **kwargs)
            list.append((img, off, anc))
            if updated:
                changed = True

        # If any have changed, render a fresh canvas
        if changed:
            self._newWidget = False
            self.image = Image.new('1', self.size)
            for img, off, anc in list:
                self._place(retainImage=True, wImage=img, offset=off, just=anc)

        return (self.image, changed)

    @staticmethod
    def _getPlacement(item):
        if len(item) == 3:
            w, o, a = item  # Extract placement, anchor and widget
        elif len(item) == 2:
            w, o = item  # or if no anchor just extract placement and widget
            a = 'lt'
        else:
            w = item[0]
            a = 'lt'
            o = (0, 0)
        return (w, o, a)


class marquee(widget):

    def __init__(self, widget=None,  resetOnChange=True, actions=('rtl',), speed=1, distance=1, tps=30, condition=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert widget, "No widget supplied to initialize scroll"

        self._timeRatio = int(speed)
        self._widget = widget
        self._resetOnChange = resetOnChange
        self._actions = []
        for a in actions:
            a = a if type(a) == tuple else (a,)
            self._actions.append(a)
        self._distance = int(distance)
        self._tps = tps
        self._timeline = []
        self._tick = 0
        self._condition = \
            self._dataset.compile(condition) if type(condition) is str else \
            condition if condition else self._shouldIMove

        self.render(force=True, move=False)

    @abc.abstractmethod
    def _shouldIMove(self, *args, **kwargs):
        pass    # pragma: no cover

    @abc.abstractmethod
    def _computeTimeline(self):
        pass    # pragma: no cover

    @abc.abstractmethod
    def _adjustWidgetSize(self):
        pass    # pragma: no cover

    # The at properties can be used by a controlling system to coordinate pauses between multiple marquee objects
    @property
    def atPause(self):
        if self._tick in self._pauses:
            return True
        return False

    @property
    def atPauseEnd(self):
        if self._tick in self._pauseEnds:
            return True
        return False

    @property
    def atStart(self):
        if not self._tick % len(self._timeline):
            return True
        return False

    def _addPause(self, length, startingPos, tickCount):
        self._pauses.append(tickCount)
        tickCount += int(length * self._tps)
        for i in range(int(length * self._tps)):
            self._timeline.append(startingPos)
        return tickCount

    def _addMovement(self, length, direction, startingPos, tickCount):
        curPos = startingPos
        self._pauseEnds.append(tickCount)

        # If this is the first timeline entry, add a starting position
        if not tickCount:
            self._timeline.append(curPos)
            tickCount = 1

        for _ in range(length // self._distance):
            dir = (self._distance, 0) if direction == 'ltr' else \
            (-self._distance, 0) if direction == 'rtl' else \
            (0, self._distance) if direction == 'ttb' else \
            (0, -self._distance)
            curPos = (curPos[0] + dir[0], curPos[1] + dir[1])

            for _ in range(self._timeRatio):
                self._timeline.append(curPos)
                tickCount += 1
        return (curPos, tickCount)

    def _reset(self):
        self._tick = 0
        self._pauses = []
        self._pauseEnds = []
        self._adjustWidgetSize()
        tx, ty = self._place(wImage=self._aWI, just=self.just)
        self._curPos = self._lastPos = (tx, ty)
        self._timeline = []
        self._computeTimeline()

    @staticmethod
    def _withinDisplayArea(pos, d):
        if ((pos[0] >= 0 and pos[0] < d[0]) or (pos[2] >= 0 and pos[2] < d[0]) or (pos[0] < 0 and pos[2] >= d[0])) and \
        ((pos[1] >= 0 and pos[1] < d[1]) or (pos[3] >= 0 and pos[3] < d[1]) or (pos[1] < 0 and pos[3] >= d[1])):
            return True
        return False

    @staticmethod
    def _enclosedWithinDisplayArea(pos, d):
        if ((pos[0] >= 0 and pos[0] <= d[0]) and (pos[2] >= 0 and pos[2] <= d[0])) and \
        ((pos[1] >= 0 and pos[1] <= d[1]) and (pos[3] >= 0 and pos[3] <= d[1])):
            return True
        return False

    @abc.abstractmethod
    def _paintScrolledWidget(self):
        pass    # pragma: no cover

    def _render(self, force=False, tick=None, move=True):
        self._tick = tick or self._tick
        img, updated = self._widget.render(force=force, tick=tick, move=move)
        if updated:
            self._adjustWidgetSize()
        if (updated and self._resetOnChange) or force:
            self._reset()
            self._tick = self._tick + 1 if move else self._tick
            return (self.image, True)

        moved = False
        self._curPos = self._timeline[self._tick % len(self._timeline)]

        if self._curPos != self._lastPos or updated:
            self.image = self._paintScrolledWidget()
            moved = True
            self._lastPos = self._curPos

        self._tick = (self._tick + 1)%len(self._timeline) if move else self._tick
        return (self.image, moved)


class slide(marquee):

    def _shouldIMove(self, *args, **kwargs):
        return self._enclosedWithinDisplayArea(
            (self._curPos[0], self._curPos[1], self._curPos[0] + self._widget.image.size[0],
            self._curPos[1] + self._widget.image.size[1]), (self.size))

    def _adjustWidgetSize(self):
        self._aWI = self._widget.image

    def _boundaryDistance(self, direction, pos):
        return \
            pos[0] if direction == 'rtl' else \
            self.size[0] - (pos[0] + self._widget.size[0]) if direction == 'ltr' else \
            pos[1] if direction == 'btt' else \
            self.size[1] - (pos[1] + self._widget.size[1])

    def _returnToStart(self, direction, curPos, tickCount):
        sp = self._timeline[0]

        dem = 0 if direction[0] == 'h' else 1
        for i in range(2):
            dir = \
                'rtl' if dem == 0 and curPos[dem] > sp[dem] else \
                'ltr' if dem == 0 and curPos[dem] < sp[dem] else \
                'btt' if dem == 1 and curPos[dem] > sp[dem] else \
                'ttb'
            curPos, tickCount = self._addMovement(abs(curPos[dem] - sp[dem]), dir, curPos, tickCount)
            dem = 0 if dem == 1 else 1

        return (curPos, tickCount)

    def _computeTimeline(self):
        if self._dataset.eval(self._condition):
            self._reprVal = 'sliding'
            tickCount = 0
            curPos = self._curPos

            for a in self._actions:
                a = a if type(a) == tuple else (a,)
                if a[0] == 'pause':
                    tickCount = self._addPause(a[1], curPos, tickCount)
                elif a[0] == 'rts':
                    dir = 'h' if len(a) == 1 else a[1]
                    curPos, tickCount = self._returnToStart(dir, curPos, tickCount)
                else:
                    distance = self._boundaryDistance(a[0], curPos) if len(a) == 1 else a[1]
                    curPos, tickCount = self._addMovement(distance, a[0], curPos, tickCount)
        else:
            self.reprVal = 'not sliding'
            self._timeline.append(self._curPos)

    def _paintScrolledWidget(self):
        img = Image.new('1', self.size)
        img.paste(self._aWI, self._curPos)
        return img


class popUp(slide):
    def __init__(self, size=None, widget=None, delay=(10, 10), *args, **kwargs):
        delay = delay if type(delay) == tuple else (delay, delay)
        range = widget.size[1] - size[1]
        actions = [('pause', delay[0]), ('btt', range), ('pause', delay[1]), ('ttb', range)]

        super().__init__(size=size, widget=widget, actions=actions, *args, **kwargs)

    def _shouldIMove(self, *args, **kwargs):
        return self._withinDisplayArea(
            (self._curPos[0], self._curPos[1], self._curPos[0] + self._widget.image.size[0],
            self._curPos[1] + self._widget.image.size[1]), (self.size))


class scroll(marquee):
    def __init__(self, gap=None, actions=('rtl',), *args, **kwargs):

        self._gap = gap if type(gap) == tuple else (gap, gap) if gap else (0, 0)

        # Figure out which directions the scroll will move so that we can inform the _computeShadowPlacements method
        dirs = [v for v in actions if (type(v) == tuple and v[0] in ['rtl', 'ltr', 'ttb', 'btt']) or v in ['rtl', 'ltr', 'ttb', 'btt']]
        h = True if ('ltr' in dirs or 'rtl' in dirs) else False
        v = True if ('ttb' in dirs or 'btt' in dirs) else False
        self._movement = (h, v)

        super().__init__(actions=actions, *args, **kwargs)

    def _shouldIMove(self, *args, **kwargs):
        if (('rtl',) in self._actions or ('ltr',) in self._actions) and self._widget.image.size[0] > self.size[0]:
            return True
        if (('btt',) in self._actions or ('ttb',) in self._actions) and self._widget.image.size[1] > self.size[1]:
            return True
        return False

    @staticmethod
    def _computeGap(gap, displaySize):
        if type(gap) in [int, float]:
            return int(round(gap))
        if type(gap) == str and gap.strip()[-1] == '%':
            return int(round((int(gap.strip()[0: -1])) / 100 * displaySize))
        return int(round(float(gap)))

    def _adjustWidgetSize(self):
        gapX = self._computeGap(self._gap[0], self.size[0])
        gapY = self._computeGap(self._gap[1], self.size[1])
        sizeX = self._widget.size[0] + gapX
        sizeY = self._widget.size[1] + gapY
        self._aWI = self._widget.image.crop((0, 0, sizeX, sizeY))

    def _computeTimeline(self):
        if self._dataset.eval(self._condition):
            self._reprVal = 'scrolling'
            tickCount = 0
            curPos = self._curPos
            for a in self._actions:
                a = a if type(a) == tuple else (a,)
                if a[0] == 'pause':
                    tickCount = self._addPause(a[1], curPos, tickCount)
                else:
                    aws = self._aWI.size[0] if a[0] in ['ltr', 'rtl'] else self._aWI.size[1]
                    curPos, tickCount = self._addMovement(aws, a[0], curPos, tickCount)

            # If position has looped back to start remove last position to prevent stutter
            if (a[0] == 'ltr' and self._timeline[-1][0] - aws == self._timeline[0][0]) or \
                (a[0] == 'rtl' and self._timeline[-1][0] + aws == self._timeline[0][0]) or \
                (a[0] == 'ttb' and self._timeline[-1][1] - aws == self._timeline[0][1]) or \
                (a[0] == 'btt' and self._timeline[-1][1] + aws == self._timeline[0][1]):
                self._timeline.pop()
        else:
            self._reprVal = 'not scrolling'
            self._timeline.append(self._curPos)

    def _computeShadowPlacements(self):
        lShadows = []
        x = (self._curPos[0] - self._aWI.size[0], self._curPos[0], self._curPos[0] + self._aWI.size[0])
        y = (self._curPos[1] - self._aWI.size[1], self._curPos[1], self._curPos[1] + self._aWI.size[1])
        a = (x[0] + self._widget.size[0] - 1, x[1] + self._widget.size[0] - 1, x[2] + self._widget.size[0] - 1)
        b = (y[0] + self._widget.size[1] - 1, y[1] + self._widget.size[1] - 1, y[2] + self._widget.size[1] - 1)

        # Determine which dimensions need to be shadowed
        xr = range(3) if self._movement[0] else range(1, 2)
        yr = range(3) if self._movement[1] else range(1, 2)

        for i in xr:
            for j in yr:
                if self._withinDisplayArea((x[i], y[j], a[i], b[j]), (self.size[0], self.size[1])):
                    lShadows.append((x[i], y[j]))
        return lShadows

    def _paintScrolledWidget(self):
        img = Image.new('1', self.size)
        pasteList = self._computeShadowPlacements()
        for p in pasteList:
            img.paste(self._aWI, p)
        return img


class staticWidget(widget):

    def __init__(self, image=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image = image

    def _render(self, force=False, *args, **kwargs):
        return (self.image, force)


class image(staticWidget):

    def __init__(self, image=None, file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        image = image or file

        if type(image) is str or type(image) is pathlib.PosixPath:
            img = Image.open(pathlib.Path(image))
            self._reprVal = f'{image}'
        else:
            self._reprVal = f'img at 0x{id(image):x}'
            img = image.copy()

        self._place(wImage=img, just=self.just)


def makeFourTupleDraw(xy):
    if len(xy) == 4:
        x0, y0, x1, y1 = xy[0], xy[1], xy[2], xy[3]
    elif len(xy) == 2:
        x0, y0, x1, y1 = xy[0][0], xy[0][1], xy[1][0], xy[1][1]
    else:
        raise ValueError(f"xy must be an array of two tuples or four integers.  Instead received {xy}")

    img = Image.new('1', (max(x0, x1) + 1, max(y0, y1) + 1))
    drw = ImageDraw.Draw(img)
    return (img, drw)


class line(staticWidget):

    def __init__(self, xy=[], fill='white', width=0, *args, **kwargs):
        super().__init__(*args, **kwargs)

        img, d = makeFourTupleDraw(xy)
        d.line(xy, fill=fill, width=width)

        self._reprVal = f'{xy}'
        self._place(wImage=img, just=self.just)


class rectangle(staticWidget):

    def __init__(self, xy=[], fill='white', outline=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        img, d = makeFourTupleDraw(xy)
        d.rectangle(xy, fill=fill, outline=outline)

        self._reprVal = f'{xy}'
        self._place(wImage=img, just=self.just)
