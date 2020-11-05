import random
import re
from collections import defaultdict
from os.path import dirname, join
import sublime
import sublime_plugin

alternate = re.compile(r'.*\(\d\)$')

completion_flags = sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS

solid_underline = sublime.DRAW_SOLID_UNDERLINE | sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
stippled_underline = sublime.DRAW_STIPPLED_UNDERLINE | sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
squiggly_underline = sublime.DRAW_SQUIGGLY_UNDERLINE | sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE

red = 'keyword'
yellow = 'string'
white = 'text'
gray = 'comment'


def rhyme_key(pronunciation):
    rhyme_key = []
    for c in reversed(pronunciation):
        if (c == '-'
                and ('0' in rhyme_key
                     or '1' in rhyme_key
                     or '2' in rhyme_key)):
            break
        rhyme_key.append(c)
    return ''.join(reversed(rhyme_key))


cmudict = {}
start_unstressed = defaultdict(lambda: defaultdict(list))
start_stressed = defaultdict(lambda: defaultdict(list))
rhymes = defaultdict(list)

for entry in open(join(dirname(__file__), 'cmudict-0.7b.txt')):
    if entry.startswith(';;;'):
        continue

    word, pronunciation = entry.rstrip().split(None, 1)

    if '-' in word:
        continue

    word = word.lower()
    pronunciation = pronunciation.lower()
    pronunciation = pronunciation.replace(' ', '-')
    cmudict[word] = pronunciation
    stress_markers = ''.join([s for s in pronunciation if s in '012'])

    if (len(stress_markers) > 10
            or '00' in stress_markers
            or '11' in stress_markers
            or '22' in stress_markers
            or '12' in stress_markers
            or '21' in stress_markers):
        continue

    if stress_markers[0] == '0':
        completions = start_unstressed
    else:
        completions = start_stressed

    completions = completions[len(stress_markers)]
    completions[''].append(word)

    for i, c in enumerate(word):
        completions[word[:i+1]].append(word)

    if stress_markers[-1] == '0':
        continue

    rhymes[rhyme_key(pronunciation)].append(word)

# for completions in start_unstressed, start_stressed:
#     syllable_counts = list(completions.keys())
#     syllable_counts.sort(reverse=True)
#     for syllable_count in syllable_counts:
#         print(syllable_count, len(completions[syllable_count]['']))


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
    stresses = [int(stress) for stress in pronunciation if stress in '012']
    return pronunciation, [(s, len(stresses)) for s in stresses]


def get_final_vowel_sound(pronunciation):
    final_vowel_sound = []
    for p in reversed(pronunciation.split('-')):
        if p == 'z':
            p = 's'
        final_vowel_sound.insert(0, p)
        if '0' in p or '1' in p or '2' in p:
            break
    return final_vowel_sound


def weighted_choice(choices):
   total = sum(w for c, w in choices)
   r = random.uniform(0, total)
   for c, w in choices:
      r -= w
      if r < 0:
         return c
   assert False, "Shouldn't get here"


class SonnetRandomEndWordsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        words_choices = []

        for syllable_count in range(1, 10):
            dct = start_unstressed if syllable_count % 2 == 0 else start_stressed
            words = dct[syllable_count]['']
            words_choices.append((words, len(words)))

        end_words = [None] * 14

        for i in range(14):
            if i in [2, 3, 6, 7, 10, 11, 13]:
                continue
            while True:
                end_words[i] = random.choice(weighted_choice(words_choices))
                j = 1 if i == 12 else 2
                k = rhyme_key(cmudict[end_words[i]])
                if len(rhymes[k]) == 1:
                    continue
                end_words[i+j] = random.choice(rhymes[k])
                if end_words[i] != end_words[i+j]:
                    break

        for row in range(14):
            line_end = self.view.line(self.view.text_point(row, 0)).end()
            word = ' ' + end_words[row]
            if line_end == self.view.size():
                word = word + '\n'
            self.view.insert(edit, line_end, word)


class Sonnet(sublime_plugin.ViewEventListener):
    @classmethod
    def is_applicable(cls, settings):
        return settings is not None and '/Text/' in settings.get('syntax', '')

    def __init__(self, view):
        super().__init__(view)
        self.meter_phantom_set = sublime.PhantomSet(view)

    def on_query_completions(self, prefix, locations):
        # print(prefix == '', [self.view.rowcol(l) for l in locations])

        # line = self.view.line(locations[0])
        # words = []
        # for raw_word in self.view.substr(line).split():
        #     words.extend(raw_word.lower().strip(',;:.?!').split('-'))

        # [s for s in words[-1] if s in '012']

        completions = start_unstressed
        if self.view.rowcol(locations[0])[1] > 1:
            prev_word_a = self.view.find_by_class(locations[0], False, sublime.CLASS_WORD_START | sublime.CLASS_LINE_START)
            prev_word_b = self.view.find_by_class(prev_word_a, True, sublime.CLASS_WORD_END | sublime.CLASS_LINE_END)
            prev_word = self.view.substr(sublime.Region(prev_word_a, prev_word_b))
            prev_word = prev_word.lower().strip(',;:.?!').split('-')[-1]
            prev_pronounce = cmudict.get(prev_word)
            if prev_pronounce:
                stress_markers = [s for s in prev_pronounce if s in '012']
                if stress_markers[-1] == '0':
                    completions = start_stressed

        replacements = []
        for syllable_count in 5, 4, 3, 2, 1:
            word = random.choice(completions[syllable_count][prefix.lower()])
            replacements.append((word, word))

        return replacements, completion_flags

        # contents = [ for word in contents.split()]

        # [''.join([stress for stress in cmudict[word] if stress in '012'])
        #     for word in contents.split()]

        #     word = 
        #         for subword in word.split('-'):
        #             p, s = cmudict_get(subword)
        #             pronunciations.append(p)
        #             stresses.extend(s)

        # replacements = completions[prefix.lower()][:7]
        # return replacements, completion_flags

    def on_post_save(self):
        print('on_post_save')
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
                    if stress in [0, 2] or word_syllables == 1:
                        stress_output[stress_index] = '<span style="color: gray">˘</span>'
                        score += 1
                    else:
                        stress_output[stress_index] = '<span style="color: yellow">¯</span>'
                else:
                    if stress > 0:
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
                p1[-1]
                p2[-1]
            except IndexError:
                continue
            if get_final_vowel_sound(p1[-1]) != get_final_vowel_sound(p2[-1]):
                rhyme_regions.append(self.view.word(line1.end()-1))
                rhyme_regions.append(self.view.word(line2.end()-1))

        self.view.add_regions('rhyme', rhyme_regions, scope=red, flags=squiggly_underline)
