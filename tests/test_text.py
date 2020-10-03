# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Test of Text Widget for the tinyDisplay system

.. versionadded:: 0.0.1
"""
import pytest
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

from tinyDisplay.render.widget import text


def test_text_widget():
    path = Path(__file__).parent / "reference/images/text_artist_sting_60x8.png"
    img = Image.open(path).convert('1')

    db = {'artist': 'Sting'}
    w = text(value='f"Artist {db[\'artist\']}"', dataset = { 'db': db }, size=(60,8))
    renderImage = w.render()[0]
    bbox = ImageChops.difference(img, renderImage).getbbox()
    assert not bbox, f'Sting image did not match'

    path = Path(__file__).parent / "reference/images/text_artist_new_republic_60x8.png"
    img = Image.open(path).convert('1')

    db['artist']='New Republic'
    renderImage = w.render()[0]
    bbox = ImageChops.difference(img, renderImage).getbbox()
    assert not bbox, f'New Republic image did not match'
