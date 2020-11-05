import mmap
import os.path
import random
import re
from functools import lru_cache

_iambic_pentameter = re.compile(r'^(0-?[12]-?){5}$')

_file = None
_mmap = None


def plugin_loaded():
    global _file, _mmap
    if _mmap is None or _mmap.closed:
        _file = open(os.path.join(os.path.dirname(__file__),
                                  'cmudict-0.7b.txt'),
                     'rb')
        _mmap = mmap.mmap(_file.fileno(), 0, access=mmap.ACCESS_READ)


def plugin_unloaded():
    _mmap.close()
    _file.close()


plugin_loaded()


alternate = re.compile(r'\(\d\)$')


class Pronunciation:
    def __init__(self, entry):
        self.entry = entry.rstrip()
        try:
            self.word, self.p = [s for s in self.entry.split('  ', 1)]
        except ValueError:
            raise ValueError(entry)
        self.word = alternate.sub('', self.word)
        self.word = self.word.lower()
        self.stress_markers = ''.join([c for c in self.p if c in '012'])
        self.rhyme_pattern = None
        if self.stress_markers[-1] == '1' or self.stress_markers[-2:] == '02':
            r = []
            for c in reversed(self.p):
                if c == ' ' and '[12]' in r:
                    break
                if c in '12':
                    r.append('[12]')
                    continue
                r.append(c)
            self.rhyme_pattern = re.compile(
                br'^\S+  .*' + ''.join(reversed(r)).encode('utf-8') + br'$',
                re.MULTILINE)

    def __repr__(self):
        return self.p.lower().replace(' ', '-')


class Meter:
    def __init__(self, stress_markers):
        line_stresses = []
        for markers in stress_markers:
            if markers == '1' and sum(len(s) for s in line_stresses) % 2 == 0:
                line_stresses.append('0')
            else:
                line_stresses.append(markers)
        self.is_iambic_pentameter = bool(
            _iambic_pentameter.match(''.join(line_stresses)))
        self.syllable_count = sum(len(s) for s in line_stresses)
        self.stress_markers = [s.replace('', ' ').strip()
                               for s in line_stresses]

    def __repr__(self):
        return '{} {} {}'.format(self.is_iambic_pentameter,
                                 self.syllable_count,
                                 self.stress_markers)


@lru_cache()
def pronounce(word):
    match = re.search(br'^' + word.encode('utf-8') + br'  .*$', 
                      _mmap,
                      re.MULTILINE | re.IGNORECASE)
    if not match:
        return None
    return Pronunciation(match.group().decode('utf-8'))


@lru_cache()
def rhyme(word1, word2):
    if word1 == word2:
        return False
    p1 = pronounce(word1).rhyme_pattern
    if not p1:
        return False
    return p1 == pronounce(word2).rhyme_pattern


def _rhymes(word):
    p1 = pronounce(word)
    if not p1.rhyme_pattern:
        return None
    for match in p1.rhyme_pattern.finditer(_mmap):
        p2 = Pronunciation(match.group().decode('utf-8'))
        if word.lower() == p2.word.lower():
            continue
        yield p2


def rhymes(word):
    for pronunciation in _rhymes(word):
        yield pronunciation.word.lower()


@lru_cache()
def meter(line):
    return Meter([pronounce(w).stress_markers for w in line.split()])


# strict_* functions == stress markers in '0', '01', '10', '010'

w0s = ['a', 'an', 'and', 'are', 'be', 'been', 'can', 'did', 'does', 'er',
       'for', 'good', 'has', 'hers', 'him', 'his', 'hm', 'hmm', "I'm", 'if',
       'in', 'is', 'it', "it's", 'its', 'just', 'of', 'or', 'than', 'that',
       'the', 'them', 'this', 'to', 'was', "who've", 'will', 'with', 'yours']


p01 = re.compile(br'^([A-Z]\S+)  [^012\n]+0[^012\n]+1[^012\n]*$', re.MULTILINE)
p10 = re.compile(br'^([A-Z]\S+)  [^012\n]+1[^012\n]+0[^012\n]*$', re.MULTILINE)
p010 = re.compile(br'^([A-Z]\S+)  [^012]+0[^012]+1[^012]+0[^012]*$', re.MULTILINE)


def strict_choices():
    p01s = [Pronunciation(m.group().decode('utf-8')) for m in p01.finditer(_mmap)]
    p10s = [Pronunciation(m.group().decode('utf-8')) for m in p10.finditer(_mmap)]
    p010s = [Pronunciation(m.group().decode('utf-8')) for m in p010.finditer(_mmap)]

    end_words = []
    for i in range(20):
        while True:
            ws = [random.choice(p01s).word.lower()]
            rs = list(strict_rhymes(ws[0]))
            if len(rs) == 0:
                continue
            if len(rs) < 7:
                ws.extend(rs)
            for i in range(7):
                ws.append(random.choice(rs))
            end_words.append(tuple(set(ws)))
            break

    other_words = []
    for ps in p01s, p10s, p010s:
        for i in range(20):
            while True:
                w = random.choice(ps).word.lower()
                if w not in end_words or w not in other_words:
                    other_words.append(w)
                    break

    for ws in end_words:
        print(ws)

    print(' '.join(other_words))
    print(' '.join(w0s))


p_rhyme = re.compile(r'[^012]+0[^012]+1[^012]*$')


def strict_rhymes(word):
    for pronunciation in _rhymes(word):
        if p_rhyme.match(str(pronunciation)):
            yield pronunciation.word.lower()
