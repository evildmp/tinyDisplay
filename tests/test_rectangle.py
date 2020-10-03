# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Test of Rectangle Widget for the tinyDisplay system

.. versionadded:: 0.0.1
"""
import pytest
from PIL import Image, ImageChops, ImageDraw

from tinyDisplay.render.widget import rectangle

def test_rectangle_widget():

    img = Image.new('1', (10, 8))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 9, 7), outline='white')

    w = rectangle(xy=(0, 0, 9, 7), outline='white', fill='black')
    renderImage = w.render()[0]
    bbox = ImageChops.difference(img, renderImage).getbbox()
    assert not bbox, f'Rectangles did not match'

    w = rectangle(xy=[(0, 0), (9, 7)], outline='white', fill='black')
    renderImage = w.render()[0]
    bbox = ImageChops.difference(img, renderImage).getbbox()
    assert not bbox, f'Rectangles did not match'
