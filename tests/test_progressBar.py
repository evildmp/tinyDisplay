# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Test of progressBar Widget for the tinyDisplay system

.. versionadded:: 0.0.1
"""
from pathlib import Path
import pytest
import time
from PIL import Image, ImageChops, ImageDraw

from tinyDisplay.render.widget import progressBar


@pytest.mark.parametrize("db, dir, range, mask, file", [\
        ({'value': 12},'ltr',(0,100), None, 'pbd12.png'), \
        ({'value': 45},'rtl',(0,90), None,  'pbd50.png'),\
        ({'value': 45},'rtl',(0,90), 'progressBar_100x8.png',  'pbm50.png'),
        ({'value': 10},'rtl',(0,100), 'progressBar_100x8.png',  'pbmrtl10.png'),
        ({'value': 35},'ttb',(0,100), 'progressBar_100x8.png',  'pbmttb35.png')
    ])
def test_defaultBar(db, dir, range, mask, file):
    # Test with default bar at various percentages, directions and ranges
    fileName = Path(__file__).parent / 'reference/images/' / file
    maskName = Path(__file__).parent / 'reference/images/' / mask if mask else None
    compImage = Image.open(fileName)
    ds = {'db': db}
    size = (100,8)

    img = progressBar(size=size, direction=dir, dataset=ds, range=range, value='db["value"]', mask=maskName).render()[0]
    bbox = ImageChops.difference(img, compImage).getbbox()
    assert bbox, f'progressBar(size={size}, direction={dir}, range={range}, value={ds["db"]["value"]}) did not match file {file}'

def test_thinBar():
    img = Image.new('1', (10,1))
    drw = ImageDraw.Draw(img)
    drw.rectangle( (0,0,4,0), fill='white')
    ds = {'db': {'value': 50}}
    pImg = progressBar(size=(10,1), dataset=ds, value='db["value"]').render()[0]

    bbox = ImageChops.difference(img, pImg).getbbox()
    assert bbox, f'Thin progressBar does not match'

def test_out_of_range():
    img = Image.new('1', (10,1))
    drw = ImageDraw.Draw(img)
    drw.rectangle( (0,0,9,0), fill='white')
    ds = {'db': {'value': 110}}
    pb = progressBar(size=(10,1), dataset=ds, value='db["value"]')
    pImg = pb.render()[0]

    bbox = ImageChops.difference(img, pImg).getbbox()
    assert bbox, f'Thin progressBar does not match'

    pImg = pb.render()[0]
    assert pImg == img, 'Unless variable changes, progressBar image shouldn\'t change'
