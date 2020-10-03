# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Test of Dataset class for the tinyDisplay system

.. versionadded:: 0.0.1
"""
import pytest, time
from tinyDisplay.utility import dataset, evaluate

updates = [
        ('db' , { 'state': 'play'} ),
        ('db' , { 'artist': 'Abba', 'title': 'Dancing Queen', 'album': 'Dancing Queen'} ),
        ('sys', { 'temp': 54.3} ),
        ('db' , { 'artist': 'Eurythmics', 'title': 'Thorn in My Side', 'album': 'Revenge'} ),
        ('db' , { 'artist': 'Talking Heads', 'title': 'Psycho Killer', 'album': 'Talking Heads'} ),
        ('sys', { 'temp': 62.8 } ),
        ('db' , { 'artist': 'Billy Joel', 'title': 'Uptown Girl', 'album': 'An Innocent Man'} ),
        ('db' , { 'artist': 'Billy Eilish', 'title': 'bad guy', 'album': 'Toggo Music'} ),
        ('sys', { 'temp': 92.6 } ),
        ('db' , { 'state': 'stop'} ),
        ('db', { 'time': time.localtime(1593626862)} )
    ]

conditions = [
    "db['state']=='play'",
    "db['artist']=='Abba'",
    "sys['temp']==54.3",
    "db['album'].lower()=='revenge'",
    "db['title'][0:5]=='Psych'",
    "sys['temp']<100",
    "db['title'].find('Girl')>=0",
    "prev.db['artist']=='Billy Joel'",
    "history('sys', -2)['temp']==54.3",
    "db['state']!=prev.db['state']",
    "time.strftime('%H:%M',db['time']) == '14:07'"
]

@pytest.mark.parametrize("updates, condition", [\
        (updates[0:1], conditions[0]), \
        (updates[0:2], conditions[1]),\
        (updates[0:3], conditions[2]),
        (updates[0:4], conditions[3]),
        (updates[0:5], conditions[4]),
        (updates[0:6], conditions[5]),
        (updates[0:7], conditions[6]),
        (updates[0:8], conditions[7]),
        (updates[0:9], conditions[8]),
        (updates[0:10], conditions[9]),
        (updates[0:11], conditions[10])
    ])
def test_dsEval(updates, condition):
    ds = dataset(historySize=5)
    for u in updates:
        ds.update(u[0], u[1])
    code = ds.compile(condition)
    ans = ds.eval(code)

    assert ans, f'{condition} failed for {updates}'
