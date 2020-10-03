# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Test of Marquee Widget for the tinyDisplay system

.. versionadded:: 0.0.1
"""
import pytest
import time
from PIL import Image, ImageChops

from tinyDisplay.utility import animate
from tinyDisplay.render.widget import text, staticText, scroll, slide, popUp


@pytest.fixture(scope='function')
def animator(request):
    cleanup = []

    def _animate(cps=60, function=None, queueSize=10):
        a = animate(cps=cps, function=function, queueSize=queueSize)
        cleanup.append(a)
        return a

    yield _animate

    for c in cleanup:
        c.stop()

@pytest.fixture(scope='function')
def makeScroll(request):

    def _make_scroll(val, size, distance=1, speed=1):
        w = text(value=val)
        sw = scroll(size=size, widget=w, actions=[('rtl')], distance=distance, speed=speed, tps=60)
        return sw

    yield _make_scroll

def test_scroll_widget_performance(animator, makeScroll):

    # Run renders for 6 seconds at 60hz and a scroll speed of 1.
    # Poll for results at 120hz
    # Should produce around 300 renders

    scrollHigh = makeScroll('High', (19, 8))
    a = animator(function=scrollHigh.render, cps=60)
    a.start()
    t = time.time()
    s = 60
    d = 5
    p = q = 0
    while t+d >= time.time():
        retval = a.get()
        p = p + 1 if retval and retval[1] else p
        time.sleep(1/120)

    expected = s*d
    received = p

    assert abs(received-expected) < .05*expected, f'Received {received} renders.  Expected {expected}'


def test_scroll_wrap_move(makeScroll):

    sw = makeScroll('High', (19,8))
    startImg = sw.render()[0]

    bbox = ImageChops.difference(sw.render()[0], startImg).getbbox()
    assert bbox, 'scroll should have moved but didn\'t'

    sw = makeScroll('Hig', (19,8))
    startImg = sw.render()[0]

    bbox = ImageChops.difference(sw.render()[0], startImg).getbbox()
    assert not bbox, 'scroll shouldn\'t have moved but did'


def test_scroll_wrap_return_to_start(makeScroll):

    sw = makeScroll('High', (19,8))
    startImg = sw.render()[0]

    images = []
    for i in range(19):
        img, res = sw.render()
        if res:
            images.append(img)

    flag = False
    for img in images:
        bbox = ImageChops.difference(img, startImg).getbbox()
        if not bbox:
            Flag = True
            break
    assert not flag, 'scroll didn\'t return to start'


@pytest.mark.parametrize("value, size, distance", [\
        ('Five!', (20, 8), 1), \
        ('Five!', (20, 8), 2), \
        ('Five!', (20, 8), 3), \
        ('Five!', (20, 8), 4), \
        ('Five!', (20, 8), 5), \
        ('Five!', (20, 8), 6), \
        ('Five!', (19, 8), 1), \
        ('Five!', (19, 8), 2), \
        ('Five!', (19, 8), 3), \
        ('Five!', (19, 8), 4), \
        ('Five!', (19, 8), 5), \
        ('Five!', (19, 8), 6), \
        ('Hello World', (25, 7), 1), \
        ('Hello World', (25, 7), 2), \
    ])
def test_scroll_distance(value, size, distance, makeScroll):
    sw = makeScroll(value, size, distance)
    w = sw._widget

    startImg = sw.render()[0]
    for i in range((w.size[0]//distance)+(1 if w.size[0]%distance else 0)):
        img, res = sw.render()
    bbox = ImageChops.difference(img, startImg).getbbox()
    assert not bbox, 'scroll didn\'t return to start'


def test_should_scroll_move(makeScroll):
    sMoved = 'scroll moved when it shouldn\'t have'
    sNotMoved = 'scroll didn\'t move when it should have'

    sw = makeScroll('High', (20,8), 1)
    w = sw._widget

    startImg = sw.render()[0]
    img = sw.render()[0]
    bbox = ImageChops.difference(img, startImg).getbbox()
    assert not bbox, sMoved

    sw = makeScroll('High', (19,8), 1)
    w = sw._widget

    startImg = sw.render()[0]
    img = sw.render()[0]
    bbox = ImageChops.difference(img, startImg).getbbox()
    assert bbox, sNotMoved

    sw = scroll(widget=w, size=(20, 4), actions=[('pause', 1), ('ttb')])
    startImg = sw.render()[0]
    img = sw.render()[0]
    bbox = ImageChops.difference(img, startImg).getbbox()
    assert not bbox, sMoved

    while not sw.atPauseEnd:
        sw.render()
    img = sw.render()[0]
    bbox = ImageChops.difference(img, startImg).getbbox()
    assert bbox, sNotMoved



@pytest.mark.parametrize("gap", [('25%'), ('4.6'), ('4')])
def test_scroll_gap(gap):
    w = staticText('Hello')
    sw = scroll(widget=w, size=(20,8), gap=gap)
    img = sw.render()[0]
    while not sw.atStart:
        img2 = sw.render()[0]

    bbox = ImageChops.difference(img, sw.render()[0]).getbbox()
    assert not bbox, 'scroll didn\'t return to start'


def test_slide1():

    w = staticText(value='This is a test!')
    sw = slide(size=(100,16), widget=w, actions=[('pause', 1),('ltr'), ('pause',2), ('rtl')], speed=1, tps=60)
    startImg = sw.render()[0]

    # Move past initial pause
    while not sw.atPauseEnd:
        img, res = sw.render()

    bbox = ImageChops.difference(sw.render()[0], startImg).getbbox()
    assert bbox, f'slide should have moved but didn\'t'

    while not sw.atStart:
        img, res = sw.render()

    bbox = ImageChops.difference(img, startImg).getbbox()
    assert not bbox, f'slide didn\'t return to start'


@pytest.mark.parametrize("value, size, moved", [\
    ('High', (20, 8), False, ), \
    ('High', (25, 8), True), \
    ('12345', (20, 8), False), \
    ('12345', (0, 0), False) ])
def test_should_slide_move(value, size, moved):
    msg = 'slide moved when it shouldn\'t have' if not moved else \
        'slide didn\'t move when it should have'
    w = staticText(value=value)
    sw = slide(size=size, widget=w, actions=[('ltr')])
    startImg = sw.render()[0]
    img = sw.render()[0]
    bbox = ImageChops.difference(img, startImg).getbbox()
    assert moved == bool(bbox), msg


@pytest.fixture(scope='function')
def slide23(request):

    def _slide(actions):
        w = text(value='This is a test!')
        sw = slide(size=(100,16), widget=w, just='mm', actions=actions, speed=1, tps=60)
        return sw

    yield _slide

def test_slide2(slide23):

    sw = slide23([('pause', 1),('ltr'), ('pause',2), ('ttb'), ('rtl'), ('btt')])
    sw.render()
    while not sw.atStart:
        img, res = sw.render()

    assert sw._curPos == (0,0), f'Slide didn\'t return to origin.  Instead it is at {sw._curPos}'


def test_slide3(slide23):

    sw = slide23([('pause', 1),('ltr'), ('pause',2), ('ttb'), ('rtl'), ('btt'), ('rts')])
    startPos = sw._curPos
    while not sw.atStart:
        img, res = sw.render()

    assert sw._curPos == startPos, f'Slide didn\'t return to origin ({startPos}).  Instead it is at {sw._curPos}'

def test_popup():
    w = staticText(value='1\n2')
    pu = popUp(size=(5,8), widget=w, delay=(.1, .1))
    top = w.image.crop((0, 0, 5, 8))
    btm = w.image.crop((0, 8, 5, 16))

    # Start at top
    assert pu.render()[0] == top

    # Move to bottom
    while not pu.atPauseEnd:
        pu.render()
    while not pu.atPause:
        pu.render()
    assert pu.render()[0] == btm

    # Move back to top
    while not pu.atPauseEnd:
        pu.render()
    while not pu.atPause:
        pu.render()
    assert pu.render()[0] == top
