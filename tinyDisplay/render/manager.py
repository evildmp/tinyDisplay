# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Manager to control the animation of the tinyDisplay system

.. versionadded:: 0.0.1
"""

import yaml
import re
import os
import pathlib
from PIL import ImageFont
from inspect import isclass, getfullargspec

from tinyDisplay.utility import dataset as Dataset
from tinyDisplay.render.sequence import sequence, collection
import tinyDisplay.render.widget as widget
from tinyDisplay.font import tdImageFont


class Loader(yaml.SafeLoader):
    def __init__(self, stream):
        self._root = os.path.split(stream.name)[0]
        super(Loader, self).__init__(stream)

    def include(self, node):
        filename = os.path.join(self._root, self.construct_scalar(node))
        with open(filename, 'r') as f:
            return yaml.load(f, Loader)


Loader.add_constructor('!include', Loader.include)


class manager():

    def __init__(self, pageFile=None, pydPageFile=None, dataset=None, displaySize=None, defaultCanvas=None):
        self.size = displaySize if displaySize else (0, 0)
        self._defaultCanvas = defaultCanvas
        self._dataset = Dataset(dataset) if dataset and type(dataset) is dict else dataset if dataset else Dataset()

        self._fonts = {}
        self._widgets = {}
        self._canvases = {}
        self._sequences = {}

        # Load valid parameters for each widget type
        self._wParams = {k: getfullargspec(v.__init__)[0][1:] for k, v in widget.__dict__.items() if isclass(v) and issubclass(v, widget.widget) and k != 'widget'}

        if pageFile:
            self._loadPageFile(pageFile)
        elif pydPageFile:
            self._loadpydPiperPageFile(pydPageFile)

    def _loadPageFile(self, filename):
        """
        Loads the pageFile configuring the WIDGETS, CANVASES, and SEQUENCES that will be animated within this Renderer
        """
        if pathlib.Path(filename).exists():
            path = pathlib.Path(filename)
        else:
            path = pathlib.Path.home() / filename
        if not path.exists():
            raise FileNotFoundError(f'Page File \'{filename}\' not found')

        f = open(path)
        self._pf = yaml.load(f, Loader)
        self._transform()

    def _loadpydPiperPageFile(self, filename):
        import importlib as il

        if pathlib.Path(filename).exists():
            path = pathlib.Path(filename)
        else:
            path = pathlib.Path.home() / filename
        if not path.exists():
            raise FileNotFoundError(f'pydPiper Page File \'{filename}\' not found')
        spec = il.util.spec_from_file_location('pf', path)
        pf = il.util.module_from_spec(spec)
        spec.loader.exec_module(pf)
        self._transformPyd(pf)
        with open(path.with_suffix('.yaml'), 'w') as file:
            yaml.safe_dump(self._pf, file)

        self._transform()

    def _createCollection(self):
        self._collection = collection(size=self.size, defaultCanvas=self._defaultCanvas)
        for name, seqConfig in self._pf['SEQUENCES'].items():
            seq = self._createSequence(name, seqConfig)
            self._collection.append(sequence=seq, placement=seqConfig.get('placement'), just=seqConfig.get('just'))

    def _createSequence(self, name, cfg):

        if name in self._sequences:
            return self._sequences[name]

        seq = sequence(name=name, condition=cfg.get('condition'), minDuration=cfg.get('minDuration'), priority=cfg.get('priority'), coolingPeriod=cfg.get('coolingPeriod'), dataset=self._dataset, defaultCanvas=self._defaultCanvas)

        for canvas in cfg['canvases']:
            c = self._createCanvas(canvas['name'])
            seq.append(c, canvas.get('duration'), canvas.get('minDuration'), canvas.get('condition'))

        self._sequences[name] = seq
        return seq

    def _createCanvas(self, name):

        if name in self._canvases:
            return self._canvases[name]

        if name in self._pf['CANVASES']:
            cfg = self._pf['CANVASES'][name]

            placements = []
            if 'placements' not in cfg:
                raise ValueError(f'Trying to create canvas {name} but there are no placements')
            for pi in cfg['placements']:
                wname, p, a = pi if len(pi) == 3 else (pi[0], pi[1], 'lt')
                w = self._createWidget(wname, self._pf['WIDGETS'][wname])
                placements.append((p, a, w))

            # name=None, size=None, placements=None
            c = widget.canvas(name, size=cfg['size'], placements=placements)
            if 'effect' in cfg:
                c = self._addEffect(c, name, cfg)
        else:
            # Perhaps the sequence is using a widget as a canvas
            if name in self._pf['WIDGETS']:
                c = self._createWidget(name, self._pf['WIDGETS'][name])
            else:
                raise ValueError(f'Cannot locate a canvas (or widget) named {name}')

        self._canvases[name] = c
        return c

    def _createWidget(self, name, cfg):

        if name in self._widgets:
            return self._widgets[name]

        # Create any needed resources
        if 'font' in cfg:
            cfg['font'] = self._createFont(cfg['font'])
        if 'mask' in cfg:
            cfg['mask'] = self._findFile(cfg['mask'], 'images')
        if 'file' in cfg:
            cfg['file'] = self._findFile(cfg['file'], 'images')
        if 'widget' in cfg:
            if type(cfg['widget']) is str:
                cfg['widget'] = self._createWidget(None, self._pf['WIDGETS'][cfg['widget']])

        if 'type' not in cfg:
            raise KeyError(f'A widget type was not provided for {name}')
        if cfg['type'] not in self._wParams:
            raise TypeError(f"{cfg['type']} is not a valid widget.  Valid values are {self._wParams.keys()}")

        cfg['name'] = name
        cfg['dataset'] = self._dataset

        kwargs = {k: v for k, v in cfg.items() if k in self._wParams[cfg['type']]}
        w = widget.__dict__[cfg['type']](**kwargs)

        if 'effect' in cfg:
            w = self._addEffect(w, name, cfg)

        if name:
            self._widgets[name] = w
        return w

    def _addEffect(self, w, name, cfg):
        if 'type' not in cfg['effect']:
            raise TypeError('Cannot add an effect to a widget without a containing type.  Options are (slide, scroll, or popUp)')
        if cfg['effect']['type'] not in ['scroll', 'slide', 'popUp']:
            raise TypeError(f"Cannot add a widget to an effect of type '{cfg['effect']['type']}'")
        cfg['effect']['widget'] = w
        w = self._createWidget(name, cfg['effect'])

        return w

    def _findFile(self, name, type):

        search = [
            pathlib.Path(self._pf['DEFAULTS']['paths'][type]) / name,
            pathlib.Path(__file__).parent / self._pf['DEFAULTS']['paths'][type] / name
        ] if 'DEFAULTS' in self._pf and 'paths' in self._pf['DEFAULTS'] else []

        search = search + \
        [
            pathlib.Path(name),
            pathlib.Path(__file__).parent / f'../{type}' / name,
        ]

        for s in search:
            if s.exists():
                return s
        raise FileNotFoundError(f'FileNotFoundError: File {name} of type \'{type}\' not found')

    def _createFont(self, name):

        if name in self._fonts:
            return self._fonts[name]

        fnt = None
        if name in self._pf['FONTS']:
            cfg = self._pf['FONTS'][name]
            if cfg['type'] == 'BMFONT':
                p = self._findFile(cfg['file'], 'fonts')
                fnt = tdImageFont(p)
            elif cfg['type'].lower() == 'truetype':
                fnt = ImageFont.truetype(cfg['file'], int(cfg['size']))
        else:
            # Assume that name is a filename instead of a reference to a font description in FONTS
            fnt = tdImageFont(self._findFile(name, 'fonts'))
        if fnt:
            self._fonts[name] = fnt
        return fnt

    @staticmethod
    def _find(key, dictionary):
        for k, v in dictionary.items():
            if k == key:
                yield (k, v, dictionary)
            elif isinstance(v, dict):
                for result in manager._find(key, v):
                    yield result
            elif isinstance(v, list):
                for d in v:
                    if isinstance(d, dict):
                        for result in manager._find(key, d):
                            yield result

    def _transformPyd(self, pydPF):
        self._pf = {}

        # FONTS
        f = {k: {'file': v['file'], 'type': 'BMFONT'} for k, v in pydPF.FONTS.items()} if 'FONTS' in pydPF.__dict__ else {}
        ttf = {k: {'file': v['file'], 'size': v['size'], 'type': 'Truetype'} for k, v in pydPF.TRUETYPE_FONTS.items()} if 'TRUETYPE_FONTS' in pydPF.__dict__ else {}

        self._pf['FONTS'] = {**f, **ttf}

        # WIDGETS
        self._pf['WIDGETS'] = pydPF.WIDGETS

        # Fix variable function
        # TODO -- handle transforms with multiple arguments (e.g. 'state|select+play+\ue000+stop+\ue001')
        def fixVariable(value):
            split_l = value.split('|')
            dbv, params = f"db['{split_l[0]}']", split_l[1:]
            stmt = dbv
            for p in params:
                args = ["'" + i + "'" for i in p.split('+')[1:]]
                cmd = p.split('+')[0].lower()
                stmt = cmd + '(' + ','.join([dbv] + args) + ')' if cmd in ['int', 'float', 'select'] else \
                    f'{{False: "no", True: "yes"}}.get(int({dbv}))' if cmd == 'yesno' else \
                    f'{{False: "false", True: "true"}}.get(int({dbv}))' if cmd == 'truefalse' else \
                    f'{{False: "off", True: "on"}}.get(int({dbv}))' if cmd == 'onoff' else \
                    stmt + '.' + cmd + '(' + ','.join(args) + ')'
            return stmt

        # Iterate through each Widget
        for k, v in self._pf['WIDGETS'].items():

            # Fix justification values
            v['just'] = {'right': 'rt', 'left': 'lt', 'center': 'mt'}.get(v.get('just', 'left'))

            # Process effects
            if 'effect' in v:
                p = v['effect']

                actions = [f'pause, {p[6]}'] if p[5].lower() != 'none' and p[6] else []
                actions.append({'left': 'rtl', 'right': 'ltr', 'up': 'btt', 'down': 'ttb'}.get(p[1]))

                # If moving left or right, X is height else X is width
                Y = v['size'][1] if 'size' in v else pydPF.FONTS[v['font']]['size'][1] if 'font' in v and 'FONTS' in pydPF.__dict__ and 'size' in pydPF.FONTS[v['font']] else None
                X = v['size'][0] if 'size' in v else None

                v['effect'] = {
                    'type': p[0],
                    'distance': p[2],
                    'speed': int(60 / p[3]),
                    'tps': 60,
                    'gap': f'{p[4]}, 0' if p[1][0] in 'lr' else f'0, {p[4]}',
                    'size': f'{p[7]}, {Y}' if p[1][0] in 'lr' else f'{X}, {p[7]}',
                    'actions': actions
                }

            # Adjust variables including the transform functions
            # (e.g. "localtime|strftime+%-I:%M" becomes "db['localtime'].strftime('%-I:%M')" )
            if 'value' in v:
                v['variables'] = [v['value']] if type(v['value']) is str else v['value']
                del (v['value'])

            if 'variables' in v:
                v['variables'] = [fixVariable(value) for value in v['variables']]

            # Lookup image names
            if v['type'] == 'progressimagebar' and 'image' in v and v['image'] in pydPF.IMAGES:
                v['mask'] = pydPF.IMAGES[v['image']]['file']
                del[v['image']]

            # Fix widget type name mismatches
            v['type'] = \
                'progressBar' if v['type'] == 'progressbar' else \
                'progressBar' if v['type'] == 'progressimagebar' else \
                'text' if v['type'] == 'ttext' else \
                'popUp' if v['type'] == 'popup' else \
                v['type']

            # Fix parameter name mismatches
            if 'rangeval' in v:
                v['range'] = v['rangeval']
                del(v['rangeval'])

                # Fix use of variables in rangeval
                v['range'] = (
                    fixVariable(v['range'][0]) if type(v['range'][0]) is str else v['range'][0],
                    fixVariable(v['range'][1]) if type(v['range'][1]) is str else v['range'][1]
                )

            # Fix media symbol values in format
            if 'format' in v:
                v['format'] = v['format'].replace('\ue000', '\u25b6')  # Play
                v['format'] = v['format'].replace('\ue001', '\u23f9')  # Stop
                v['format'] = v['format'].replace('\ue002', '\u25b6')  # Random
                v['format'] = v['format'].replace('\ue003', '\U0001f502')  # Repeat Once
                v['format'] = v['format'].replace('\ue004', '\U0001f501')  # Repeat All
                v['format'] = v['format'].replace('\ue005', '\U0001f525')  # Fire

        # IMAGES
        if 'IMAGES' in pydPF.__dict__:
            for name, value in pydPF.IMAGES.items():
                self._pf['WIDGETS'][name] = {'type': 'image', 'file': value['file']}

        # CANVASES
        if 'CANVASES' in pydPF.__dict__:
            self._pf['CANVASES'] = {}
            for name, value in pydPF.CANVASES.items():
                if 'widgets' in value:
                    pl = []
                    for w, x, y in value['widgets']:
                        pl.append(f'{w}, {x}, {y}')
                if 'size' in value:
                    sz = f"{value['size'][0]}, {value['size'][1]}"
                ef = {
                    'type': 'popUp',
                    'size': f"{value['size'][0]}, {value['effect'][1]}",
                    'delay': f"{value['effect'][2]}, {value['effect'][3]}"
                } if 'effect' in value and value['effect'][0].lower() == 'popup' else None

                self._pf['CANVASES'][name] = {'placements': pl, 'size': sz}
                if ef:
                    self._pf['CANVASES'][name]['effect'] = ef

        # SEQUENCES
        if 'SEQUENCES' in pydPF.__dict__:
            self._pf['SEQUENCES'] = {}

            # Set priority in ascending order in list (e.g. last is highest)
            priority = len(pydPF.SEQUENCES)

            for value in pydPF.SEQUENCES:
                name = value['name']
                self._pf['SEQUENCES'][name] = {'name': name}
                if 'minimum' in value:
                    self._pf['SEQUENCES'][name]['minDuration'] = value['minimum']
                if 'coordinates' in value:
                    self._pf['SEQUENCES'][name]['placement'] = f"{value['coordinates'][0]}, {value['coordinates'][1]}"
                if 'canvases' in value:
                    self._pf['SEQUENCES'][name]['canvases'] = [{'name': v['name'], 'duration': v.get('duration', 1), 'condition': v.get('conditional', 'True')} for v in value['canvases']]
                if 'conditional' in value:
                    self._pf['SEQUENCES'][name]['condition'] = value['conditional'].replace('dbp', 'prev.db')
                if 'coolingperiod' in value:
                    self._pf['SEQUENCES'][name]['coolingPeriod'] = value['coolingperiod']
                self._pf['SEQUENCES'][name]['priority'] = priority
                priority -= 1

    def _transform(self):
        # Convert Single line fonts in the format "{ 'name': 'filename' }" into standard format (e.g. { 'name': { 'file': 'filename', 'type':'BMFONT'}})
        self._pf['FONTS'] = {k: {'file': v, 'type': 'BMFONT'} if type(v) is str else v for k, v in self._pf['FONTS'].items()}

        # Convert sizes into tuples
        for k, v, d in self._find('size', self._pf):
            if type(v) is str and len(v.split(',')) > 1:
                d[k] = tuple([int(v.strip()) for v in v.split(',')])

        # Convert actions into tuples
        for k, v, d in self._find('actions', self._pf):
            if type(v) is list:
                d[k] = [(i.split(',')[0], int(i.split(',')[1])) if type(i) is str and len(i.split(',')) == 2 else
                i for i in v]

        # Convert placements into tuples
        for k, v, d in self._find('placements', self._pf):
            if type(v) is list:
                d[k] = [(i.split(',')[0], tuple([int(i) for i in i.split(',')[1:3]])) if type(i) is str and len(i.split(',')) == 3 else
                (i.split(',')[0], tuple([int(i) for i in i.split(',')[1:3]]), i.split(',')[3].strip("' \n")) if type(i) is str and len(i.split(',')) == 4 else
                i for i in v]

        # Convert placement into tuples
        for k, v, d in self._find('placement', self._pf):
            if type(v) is str and len(v.split(',')) > 1:
                d[k] = tuple([int(v) for v in v.split(',')])

        # Convert gap into tuples
        for k, v, d in self._find('gap', self._pf):
            if type(v) is str and len(v.split(',')) > 1:
                d[k] = tuple([v for v in v.split(',')])

        # Convert delay into tuples
        for k, v, d in self._find('delay', self._pf):
            if type(v) is str and len(v.split(',')) > 1:
                d[k] = tuple([int(v) for v in v.split(',')])

        # Convert singleton variables into lists
        for k, v, d in self._find('variables', self._pf):
            if type(v) is str:
                d[k] = [v]

    @staticmethod
    def _replaceVars(s, d):
        p = re.compile('{.+?}')
        rl = p.findall(p)
        vl = [i[1:-1] for i in rl]
        for i in range(len(vl)):
            if vl[i] in d:
                s = s.replace(rl[i], d[vl[i]])
        return s

    @staticmethod
    def _replaceFile(s):
        p = re.compile('file\\(.+?\\)')   # Find a file(...) instance
        m = p.search(s)
        # If we do, attempt to open a file and replace the reference of file with the contents of the file
        if m:
            with open(m.group(0)[5:-1].strip("'\""), 'r') as f:
                ss = " ".join([x.strip() for x in f])
            s = s.replace(m.group(0), ss)
        return s

    @staticmethod
    def _addDefaults(vType, d, vDefaults, keys):
        # Get widget specific defaults if they exist and are needed
        if vType in vDefaults:
            for k in keys:
                if k in vDefaults[vType] and k not in d:
                    d[k] = vDefaults[vType][k]

        # Get general widget defaults for remaining missing values
        for k in keys:
            if k in vDefaults and k not in d:
                d[k] = vDefaults[k]
        return d
