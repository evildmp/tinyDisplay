# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Test of Line Widget for the tinyDisplay system

.. versionadded:: 0.0.1
"""
import pytest
from PIL import Image, ImageChops, ImageDraw

from tinyDisplay.render.widget import line

def test_line_widget():

    img = Image.new('1', (10, 8))
    d = ImageDraw.Draw(img)
    d.line( [(0, 0), (49, 49)], fill='white')

    w = line(xy=[(0, 0), (49, 49)], fill='white')
    renderImage = w.render()[0]
    bbox = ImageChops.difference(img, renderImage).getbbox()
    assert not bbox, f'Rectangles did not match'

    w = line(xy=(0, 0, 49, 49), fill='white')
    renderImage = w.render()[0]
    bbox = ImageChops.difference(img, renderImage).getbbox()
    assert not bbox, f'Rectangles did not match'
