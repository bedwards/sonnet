import mmap
import os.path
import re
from functools import lru_cache

iambic_pentameter = re.compile(r'^(0-?[12]-?){5}$')


class Pronunciation:
    def __init__(self, entry):
        try:
            self.word, self.p = [s for s in entry.rstrip().split('  ', 1)]
        except ValueError:
            raise ValueError(entry)
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
            self.rhyme_pattern = re.compile(br'^\S+  .*' + ''.join(reversed(r)).encode('utf-8') + br'$', re.MULTILINE)

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
        self.is_iambic_pentameter = bool(iambic_pentameter.match(''.join(line_stresses)))
        self.syllable_count = sum(len(s) for s in line_stresses)
        self.stress_markers = [s.replace('', ' ').strip() for s in line_stresses]

    def __repr__(self):
        return '{} {} {}'.format(self.is_iambic_pentameter, self.syllable_count, self.stress_markers)


class PronouncingDictionary:
    def __init__(self):
        self.file = open(os.path.join(os.path.dirname(__file__), 'cmudict-0.7b.txt'), 'rb')
        self.mmap = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)

    def close(self):
        self.mmap.close()
        self.file.close()

    @lru_cache(maxsize=128)
    def pronounce(self, word):
        match = re.search(br'^' + word.encode('utf-8') + br'  .*$', self.mmap, re.MULTILINE | re.IGNORECASE)
        if not match:
            return None
        return Pronunciation(match.group(0).decode('utf-8'))

    @lru_cache(maxsize=128)
    def rhyme(self, word1, word2):
        if word1 == word2:
            return False
        p1 = self.pronounce(word1).rhyme_pattern
        if not p1:
            return False
        return p1 == self.pronounce(word2).rhyme_pattern

    def rhymes(self, word):
        p = self.pronounce(word)
        if not p.rhyme_pattern:
            return None
        for match in p.rhyme_pattern.finditer(self.mmap):
            w = Pronunciation(match.group(0).decode('utf-8')).word.lower()
            if word.lower() == w:
                continue
            yield w

    @lru_cache(maxsize=128)
    def meter(self, line):
        return Meter([self.pronounce(w).stress_markers for w in line.split()])
