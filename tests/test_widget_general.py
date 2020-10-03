# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Test of Image Widget for the tinyDisplay system

.. versionadded:: 0.0.1
"""
import pytest
from PIL import Image, ImageChops, ImageDraw

from tinyDisplay.render.widget import text, staticText, rectangle

def test_image_placement():

    # Make H
    hImg = Image.new('1', (5,8))
    d = ImageDraw.Draw(hImg)
    d.line([(0,1),(0,7)], fill='white')
    d.line([(4,1),(4,7)], fill='white')
    d.line([(0,4),(4,4)], fill='white')

    w = text(value='H', size=(100,16), just='rt')
    renderImage = w.render()[0]

    for size in [(100,16), (99,15), (20,8), (19,8)]:
        for j in ['lt', 'lm', 'lb', 'mt', 'mm', 'mb', 'rt', 'rm', 'rb']:
            offsetH = { 'r': size[0]-5, 'l': 0, 'm': round((size[0]-5)/2) }
            offsetV = { 'b': size[1]-8, 't': 0, 'm': round((size[1]-8)/2) }

            w = text(value='H', size=size, just=j)
            renderImage = w.render()[0]

            img = Image.new('1', size)
            img.paste(hImg, (offsetH[j[0]],offsetV[j[1]]) )
            bbox = ImageChops.difference(img, renderImage).getbbox()
            assert not bbox, f'Place {j[0]},{j[1]} failed at size {size}'

def test_clear():
    w = rectangle((0, 0, 10, 10))
    img = Image.new('1', (11,11), 0)
    drw = ImageDraw.Draw(img)
    drw.rectangle((0, 0, 10, 10), fill='white')
    assert w.render()[0] == img

    w.clear()
    img = Image.new('1', (11, 11))
    assert w.render()[0] == img


def test_repr():
    w = staticText(name='STATIC12345', value='12345')
    v = '<STATIC12345.staticText value(\'12345\') size(25, 8)'
    assert f'{w}'[0:len(v)] == v, f'Unexpected repr value given: {w}'


def test_string_eval():
    s = 'abc'
    w = text(value=s)
    img1 = w.render()[0]
    drw = ImageDraw.Draw(img1)
    img2 = Image.new('1', drw.textsize(s, font=w.font))
    drw = ImageDraw.Draw(img2)
    drw.text((0, 0), s, font=w.font, fill='white')

    assert img1 == img2, f'Images do not match for value {w.current}'


def test_request_size():
    s = 'abc'
    w = text('abc', size=(10,8))
    img1 = w.render()[0]
    drw = ImageDraw.Draw(img1)
    img2 = Image.new('1', (10, 8))
    drw = ImageDraw.Draw(img2)
    drw.text((0, 0), s, font=w.font, fill='white')

    assert img1 == img2, f'Image should only contain \'ab\''

    db = {'value': s}
    w = text(value='f"{db[\'value\']}"', dataset = { 'db': db }, size=(10,8))
    w.render()[0]
    db['value']= s[0]
    img1 = w.render()[0]
    img2 = Image.new('1', (10, 8))
    drw = ImageDraw.Draw(img2)
    drw.text((0, 0), s[0], font=w.font, fill='white')

    assert img1 == img2, f'Image should still only contain \'ab\''


def test_bad_four_tuple():
    with pytest.raises(ValueError) as ex:
        w = rectangle( (0, 1, 2, 3, 4), fill='black', outline='white')
    assert str(ex.value) == \
        "xy must be an array of two tuples or four integers.  Instead received (0, 1, 2, 3, 4)"
