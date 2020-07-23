import re
from collections import defaultdict
from os.path import dirname, join
import sublime
from sublime_plugin import ViewEventListener

alternate = re.compile(r'.*\(\d\)$')

bit_flags = 0
# bit_flags = sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS

solid_underline = sublime.DRAW_SOLID_UNDERLINE | sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
stippled_underline = sublime.DRAW_STIPPLED_UNDERLINE | sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
squiggly_underline = sublime.DRAW_SQUIGGLY_UNDERLINE | sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE

red = 'keyword'
yellow = 'string'
white = 'text'
gray = 'comment'

cmudict = {}
completions = defaultdict(list)
for entry in open(join(dirname(__file__), 'cmudict-0.7b.txt')):
    if entry.startswith(';;;'):
        continue
    word, pronunciation = entry.rstrip().split(None, 1)
    word = word.lower()
    pronunciation = pronunciation.lower()
    if alternate.match(word):
        continue
    cmudict[word] = pronunciation
    for i, c in enumerate(word):
        completions[word[:i+1]].append((word, word))

def _cmudict_get(word):
    if word in cmudict:
        return cmudict[word]

    if word == "wh'r":
        return cmudict['whether']

    if word == 'burthen':
        return cmudict['burden']

    w = word.replace("'d", "ed")
    if w in cmudict:
        return cmudict[w]

    w = word.replace('ou', 'o')
    if w in cmudict:
        return cmudict[w]

    return None

def cmudict_get(word):
    pronunciation = _cmudict_get(word)
    if pronunciation is None:
        return '?', [(None, None)]
    pronunciation = pronunciation.replace(' ', '-')
    stresses = [int(stress) for stress in pronunciation if stress in '012']
    return pronunciation, [(s, len(stresses)) for s in stresses]


def get_final_vowel_sound(pronunciation):
    final_vowel_sound = []
    for p in reversed(pronunciation.split('-')):
        if p == 'z':
            p = 's'
        final_vowel_sound.insert(0, p)
        if '0' in p or '1' in p:
            break
    return final_vowel_sound


class Sonnet(ViewEventListener):
    @classmethod
    def is_applicable(cls, settings):
        return settings is not None and '/Text/' in settings.get('syntax', '')

    def __init__(self, view):
        super().__init__(view)
        self.meter_phantom_set = sublime.PhantomSet(view)
        # self.rhyme_phantom_set = sublime.PhantomSet(view)
        self.on_modified_async()

    def on_query_completions(self, prefix, locations):
        print(prefix, [self.view.rowcol(l) for l in locations])
        replacements = completions[prefix.lower()][:7]
        return replacements, bit_flags

    def on_modified_async(self):

        line_contents = []
        longest_line = 0

        for row in range(14):
            point = self.view.text_point(row, 0)
            if point >= self.view.size():
                break
            line = self.view.line(point)
            contents = self.view.substr(line)
            line_contents.append((line, contents))
            if len(contents) > longest_line:
                longest_line = len(contents)


        line_pronunciations = []
        meter_phantoms = []

        for line, content in line_contents:
            pronunciations = []
            stresses = []

            for word in content.split():
                word = word.strip(',;:.?!').lower()
                for subword in word.split('-'):
                    p, s = cmudict_get(subword)
                    pronunciations.append(p)
                    stresses.extend(s)

            line_pronunciations.append((line, pronunciations))

            score = 0
            cur_syllable = 1
            total_syllables = 0
            word_start_offset = len(content) - len(content.lstrip())
            word_starts = [word_start_offset] + [m.start() + word_start_offset + 1 for m in re.finditer('[ -]', content.lstrip())]
            cur_word = 0
            stress_output = ['&nbsp;'] * longest_line
            stress_index = 0
            for i, (stress, word_syllables) in enumerate(stresses):
                if stress is None:
                    continue
                stress_index = word_starts[cur_word] + (cur_syllable - 1) * 2
                if i % 2 == 0:
                    if stress == 0 or word_syllables == 1:
                        stress_output[stress_index] = '<span style="color: gray">˘</span>'
                        score += 1
                    else:
                        stress_output[stress_index] = '<span style="color: yellow">¯</span>'
                else:
                    if stress >= 1:
                        stress_output[stress_index] = '<span style="color: gray">¯</span>'
                        score += 1
                    else:
                        stress_output[stress_index] = '<span style="color: yellow">˘</span>'
                if cur_syllable == word_syllables:
                    total_syllables += cur_syllable
                    cur_syllable = 1
                    cur_word += 1
                else:
                    cur_syllable += 1

            meter_summary = '<span style="color: {}">(' + '{:>2}'.format(score) + '/' + '{:>2}'.format(total_syllables) + ')</span>'
            if score == 10 and total_syllables == 10:
                meter_summary = meter_summary.format('gray')
            else:
                meter_summary = meter_summary.format('yellow')

            meter_phantom_content = ''.join(stress_output) + '&nbsp;' * 4 + meter_summary
            meter_phantoms.append(sublime.Phantom(line, meter_phantom_content, sublime.LAYOUT_BLOCK))

        self.meter_phantom_set.update(meter_phantoms)

        rhyme_regions = []

        for i, j in (0,2), (1,3), (4,6), (5,7), (8,10), (9,11), (12,13):
            try:
                line1, p1 = line_pronunciations[i]
                line2, p2 = line_pronunciations[j]
            except IndexError:
                continue
            if get_final_vowel_sound(p1[-1]) != get_final_vowel_sound(p2[-1]):
                rhyme_regions.append(self.view.word(line1.end()-1))
                rhyme_regions.append(self.view.word(line2.end()-1))

        self.view.add_regions('rhyme', rhyme_regions, scope=red, flags=squiggly_underline)