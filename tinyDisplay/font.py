# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Font functions to support tinyDisplay

Mainly to support pydPiper's (hacked) BMFONT implementation
and multipage (e.g. >256 char) font files

.. versionadded:: 0.0.1
"""

from PIL import FontFile, Image, ImageFont
import pathlib

# Modify Pillow ImageFont to support BMFONTS with more than 256 characters


def _readGlyphData(fileName):

    """
    Read glyph data from BMFont file

    :param fp: file pointer associated with font file
    :type fp:

    :return: tuple of line height and dictionary of glyph data tuples containing glyph advance, offset, size, and image indexed by glyph unicode value
    :rtype: tuple(int, dict)
    """

    fp = open(fileName)
    s = fp.readline()  # info face="upperascii" size=6 bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=0 aa=1 padding=0,0,0,0 spacing=0,0
    if s[:9] != "info face":
        raise SyntaxError("not a valid BMFONT file")
    s = fp.readline()  # common lineHeight=5 base=6 scaleW=80 scaleH=30 pages=1 packed=0
    lineHeight = int(s.split()[1].split('=')[1])

    def _readGlyphPage(fp, filename, pages, count, glyphs):
        """
        Internal function that retrieves a page worth of glyphs
        """
        from os.path import dirname

        sketches = {}
        for p, fn in pages.items():
            try:
                sketches[p] = Image.open(fn)
            except FileNotFoundError:
                sketches[p] = Image.open(dirname(fileName) + '/' + fn)
            sketches[p].convert(mode='1')

        i = 0
        for s in fp:
            s = s.strip()  # char id=8 x=48 y=0 width=5 height=8 xoffset=0 yoffset=0 xadvance=5 page=0 chnl=0 # 'x': Lowercase X
            if s == '' or s[0] == '#':
                # Skip empty lines or lines that start with a '#'
                continue
            i += 1
            if i > count:
                break
            db = {x: y for x, y in (x.split('=') for x in s.split('#')[0].split()[1:])}

            w, h, l, d = int(db['width']), int(db['height']), int(db['xoffset']), int(db['yoffset'])
            x, y = int(db['x']), int(db['y'])
            dx, dy = int(db['xadvance']), 0
            try:
                ch = int(db['id'])
            except ValueError:
                ch = int(db['id'], 16)
            p = int(db['page'])

            gImg = sketches[p].crop((x, y, x + w, y + h))

            glyphs[ch] = (dx, dy), (l, -d - h, w + l, -d), (0, 0, w, h), gImg

        return glyphs

    glyphs = {}
    pages = {}
    for s in fp:  # page id=0 file="upperasciiwide_3x5.png"
        if s[0:4].lower() == 'page':
            pages[int(s.split()[1].split('=')[1])] = s.split()[2].split('=')[1].strip('"\'')
        else:
            if s[0:5].lower() == 'chars':
                count = int(s.split()[1].split('=')[1])
            break
            raise ValueError(f'Expected chars count line.  Received {s}')

    glyphs = _readGlyphPage(fp, fileName, pages, count, glyphs)

    return (lineHeight, glyphs)


class tdImageFont(ImageFont.ImageFont):
    def __init__(self, fileName, defaultChar=' ', *args, **kwargs):
        self._defaultChar = defaultChar
        self.load(fileName, **kwargs)

    def load(self, fileName, *args, **kwargs):
        """
        Load BMFONT file
        """
        self.lineHeight, self.tdGlyphs = _readGlyphData(fileName)
        self.xadvance = kwargs['xadvance'] if 'xadvance' in kwargs else None

    def getsize(self, text, *args, **kwargs):
        """
        Get the size that the rendered text will require
        """
        xsize = xLineSize = 0
        ysize = yLineSize = 0

        for line in text.split('\n'):
            xLineSize = 0
            yLineSize = self.lineHeight
            for s in line:
                i = ord(s) if ord(s) in self.tdGlyphs else ord(self._defaultChar)
                xLineSize += self.xadvance if self.xadvance else self.tdGlyphs[i][0][0]
                yLineSize = max(yLineSize, self.tdGlyphs[i][2][3])
            xsize = max(xsize, xLineSize)
            ysize += yLineSize
        return ((xsize, ysize))

    def getmask(self, text, mode="", *args, **kwargs):
        img = Image.new("1", self.getsize(text))
        yp = 0
        for line in text.split('\n'):
            ls = self.getsize(line)
            xp = 0
            yp += ls[1]
            for s in line:
                i = ord(s) if ord(s) in self.tdGlyphs else ord(self._defaultChar)
                img.paste(self.tdGlyphs[i][3], (xp + self.tdGlyphs[i][1][0], yp + self.tdGlyphs[i][1][1]))
                xp += self.xadvance if self.xadvance else self.tdGlyphs[i][0][0]
        img.load()
        self.gmImage = img
        return img.im


# Convert pydPiper's broken BMFONT format to Pillow's PIL format (or the BDF format)
class tdBMFontFile(FontFile.FontFile):
    def __init__(self, fileName):
        super().__init__()

        self.lineHeight, self.tdGlyphs = _readGlyphData(fileName)
        w = 0
        self.pixelSize = 0
        for k, v in self.tdGlyphs.items():
            if int(k) < 256:
                self.glyph[int(k)] = v
            w += v[2][2]  # add width
            self.pixelSize = max(self.pixelSize, v[2][3])
        self.avgWidth = w // len(self.tdGlyphs)

    def saveBDF(self, fileName=None, familyName=None, weight='Medium', slant='R', pixelSize=8, resolution=(75, 75), spacing='C'):

        foundry = 'tinyDisplay'

        cnt = len(self.tdGlyphs)
        # BDF Header Values
        START = 'STARTFONT 2.1'
        FONT = f'FONT -{foundry}-{familyName}-{weight}-{slant}-Normal--{self.pixelSize}-{self.pixelSize*10}-{resolution[0]}-{resolution[1]}-{spacing}-{self.avgWidth}-ISO10646-1'
        SIZE = f'SIZE {self.lineHeight} {resolution[0]} {resolution[1]}'
        FONTBOUNDINGBOX = f'FONTBOUNDINGBOX {self.avgWidth} {self.lineHeight} 0 0'
        PROPERTIES = f'STARTPROPERTIES 2\nFONT_ASCENT {self.lineHeight}\nFONT_DESCENT 0\nENDPROPERTIES'
        CHARS = f'CHARS {cnt}'

        HEADER = \
            START + '\n' + \
            FONT + '\n' + \
            SIZE + '\n' + \
            FONTBOUNDINGBOX + '\n' +\
            PROPERTIES + '\n' + \
            CHARS + '\n'

        p = pathlib.Path(fileName)
        with open(p, 'wb') as f:
            f.write(HEADER.encode('utf-8'))
            for k, v in self.tdGlyphs.items():
                # v = (dx, dy), (l, -d - h, w + l, -d), (0, 0, w, h), gImg
                STARTCHAR = f'STARTCHAR U+{k:08x}' if k > 0xFFFF else f'STARTCHAR u+{k:04x}'
                ENCODING = f'ENCODING {k}'
                SWIDTH = f'SWIDTH {v[2][2] // self.avgWidth * 1000} 0'  # sw = v[2][2]/avgWidth * 1000
                DWIDTH = f'DWIDTH {v[2][2]} 0'
                BBX = f'BBX {v[2][2]} {v[2][3]} {v[1][0]} {-v[1][3]}'
                DATA = 'BITMAP\n' + '\n'.join([f'{i:02x}' for i in list(v[3].tobytes('raw', '1'))])

                CHARDATA = \
                    STARTCHAR + '\n' + \
                    ENCODING + '\n' + \
                    SWIDTH + '\n' + \
                    DWIDTH + '\n' + \
                    BBX + '\n' + \
                    DATA + '\nENDCHAR\n'
                f.write(CHARDATA.encode('utf-8'))
            f.write('ENDFONT\n'.encode('utf-8'))
