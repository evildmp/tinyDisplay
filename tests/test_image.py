# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Test of Image Widget for the tinyDisplay system

.. versionadded:: 0.0.1
"""
import pytest
from pathlib import Path
from PIL import Image, ImageChops

from tinyDisplay.render.widget import image

def test_image_widget():
    path = Path(__file__).parent / "reference/images/pydPiper_splash.png"
    img = Image.open(path).convert('1')

    w = image(size=img.size, image=img)
    renderImage = w.render()[0]
    bbox = ImageChops.difference(img, renderImage).getbbox()
    assert not bbox, f'{path} did not match image within widget'

    w = image(image=path)
    renderImage = w.render()[0].convert('1')
    bbox = ImageChops.difference(img, renderImage).getbbox()
    assert not bbox, f'{path} did not match image within widget'
