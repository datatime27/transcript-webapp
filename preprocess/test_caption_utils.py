import unittest
from caption_utils import strip_music_markers, split_multi_speaker_captions, split_into_sentences, normalize_soundeffect_captions


class TestStripMusicMarkers(unittest.TestCase):

    def _cap(self, text):
        return {'text': text, 'start': 0.0, 'duration': 1.0}

    def test_removes_hash(self):
        result = strip_music_markers([self._cap("# I'll give you a clue! #")])
        self.assertEqual(result[0]['text'], " I'll give you a clue! ")

    def test_no_hash_unchanged(self):
        result = strip_music_markers([self._cap('Hello there.')])
        self.assertEqual(result[0]['text'], 'Hello there.')

    def test_other_fields_preserved(self):
        cap = {'text': '# la la #', 'start': 5.0, 'duration': 2.0, 'speaker': 'GREG'}
        result = strip_music_markers([cap])
        self.assertEqual(result[0], {'text': ' la la ', 'start': 5.0, 'duration': 2.0, 'speaker': 'GREG'})

    def test_original_not_mutated(self):
        cap = self._cap('# la la #')
        strip_music_markers([cap])
        self.assertEqual(cap['text'], '# la la #')

    def test_empty_list(self):
        self.assertEqual(strip_music_markers([]), [])

    def test_high_pitched_pipeline(self):
        caps = [{'text': "HIGH-PITCHED:\n# I'll give you a clue! #", 'start': 0.0, 'duration': 3.0}]
        result = normalize_soundeffect_captions(split_into_sentences(split_multi_speaker_captions(strip_music_markers(caps))))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], "[HIGH-PITCHED]: I'll give you a clue!")


class TestSplitMultiSpeakerCaptions(unittest.TestCase):

    # ── No split ──────────────────────────────────────────────────────────

    def test_single_speaker_unchanged(self):
        result = split_multi_speaker_captions([
            {
                'text':     'Hello there.',
                'start':    0.0,
                'duration': 2.0,
            },
        ])
        self.assertEqual(result, [
            {
                'text':     'Hello there.',
                'start':    0.0,
                'duration': 2.0,
            },
        ])

    def test_preserves_extra_fields(self):
        result = split_multi_speaker_captions([
            {
                'text':     'Hello.',
                'start':    0.0,
                'duration': 2.0,
                'speaker':  'GREG',
            },
        ])
        self.assertEqual(result, [
            {
                'text':     'Hello.',
                'start':    0.0,
                'duration': 2.0,
                'speaker':  'GREG',
            },
        ])

    def test_dash_mid_sentence_no_split(self):
        result = split_multi_speaker_captions([
            {
                'text':     "Well - I don't know.",
                'start':    0.0,
                'duration': 2.0,
            },
        ])
        self.assertEqual(result, [
            {
                'text':     "Well - I don't know.",
                'start':    0.0,
                'duration': 2.0,
            },
        ])

    def test_html_preserved_when_no_split(self):
        result = split_multi_speaker_captions([
            {
                'text':     'Welcome to<i> Taskmaster,</i> a fun entertainment show',
                'start':    0.0,
                'duration': 2.0,
            },
        ])
        self.assertEqual(result, [
            {
                'text':     'Welcome to<i> Taskmaster,</i> a fun entertainment show',
                'start':    0.0,
                'duration': 2.0,
            },
        ])

    # ── Plain text \n- format ─────────────────────────────────────────────

    def test_plain_newline_dash(self):
        # Equal length parts → equal durations
        result = split_multi_speaker_captions([
            {
                'text':     'AAAA\n- BBBB',
                'start':    0.0,
                'duration': 2.0,
            },
        ])
        self.assertEqual(result, [
            {'text': 'AAAA', 'start': 0.0, 'duration': 1.0},
            {'text': 'BBBB', 'start': 1.0, 'duration': 1.0},
        ])

    def test_plain_newline_dash_leading_dash_stripped(self):
        result = split_multi_speaker_captions([
            {
                'text':     '-AAAA\n- BBBB',
                'start':    0.0,
                'duration': 2.0,
            },
        ])
        self.assertEqual(result, [
            {'text': 'AAAA', 'start': 0.0, 'duration': 1.0},
            {'text': 'BBBB', 'start': 1.0, 'duration': 1.0},
        ])

    def test_literal_backslash_n(self):
        result = split_multi_speaker_captions([
            {
                'text':     'AAAA\\n- BBBB',
                'start':    0.0,
                'duration': 2.0,
            },
        ])
        self.assertEqual(result, [
            {'text': 'AAAA', 'start': 0.0, 'duration': 1.0},
            {'text': 'BBBB', 'start': 1.0, 'duration': 1.0},
        ])

    # ── HTML format ───────────────────────────────────────────────────────

    def test_html_italic_dash_with_closing_tag(self):
        # part0: trailing <i> removed; part1: leading </i> removed, inner <i>...</i> preserved
        result = split_multi_speaker_captions([
            {
                'text':     '-Face?<i>\n -</i> [male voice]<i> I have a face.</i>',
                'start':    0.0,
                'duration': 3.2,
            },
        ])
        self.assertEqual([c['text'] for c in result], [
            'Face?',
            '[male voice]<i> I have a face.</i>',
        ])

    def test_html_italic_dash_without_closing_tag(self):
        # part0: trailing <i> removed; part1: trailing </i> removed (no matching opener)
        result = split_multi_speaker_captions([
            {
                'text':     '-Chin?<i>\n -I have three chins.</i>',
                'start':    0.0,
                'duration': 2.4,
            },
        ])
        self.assertEqual([c['text'] for c in result], [
            'Chin?',
            'I have three chins.',
        ])

    def test_html_preserved_in_unsplit_caption(self):
        result = split_multi_speaker_captions([
            {
                'text':     '<i>Hello there.</i>',
                'start':    0.0,
                'duration': 2.0,
            },
        ])
        self.assertEqual(result, [
            {
                'text':     '<i>Hello there.</i>',
                'start':    0.0,
                'duration': 2.0,
            },
        ])

    # ── Timecodes ─────────────────────────────────────────────────────────

    def test_start_times(self):
        result = split_multi_speaker_captions([
            {
                'text':     'AAAA\n- BBBB',
                'start':    10.0,
                'duration': 2.0,
            },
        ])
        self.assertEqual(result, [
            {'text': 'AAAA', 'start': 10.0, 'duration': 1.0},
            {'text': 'BBBB', 'start': 11.0, 'duration': 1.0},
        ])

    def test_durations_proportional_to_text_length(self):
        # "AB" (2) and "ABCD" (4) → 1/3 and 2/3 of 3.0
        result = split_multi_speaker_captions([
            {
                'text':     'AB\n- ABCD',
                'start':    0.0,
                'duration': 3.0,
            },
        ])
        self.assertEqual(result, [
            {'text': 'AB',   'start': 0.0, 'duration': 1.0},
            {'text': 'ABCD', 'start': 1.0, 'duration': 2.0},
        ])

    # ── Multiple captions ─────────────────────────────────────────────────

    def test_mixed_list(self):
        result = split_multi_speaker_captions([
            {
                'text':     'Single caption.',
                'start':    0.0,
                'duration': 1.0,
            },
            {
                'text':     'AAAA\n- BBBB',
                'start':    1.0,
                'duration': 2.0,
            },
        ])
        self.assertEqual(result, [
            {'text': 'Single caption.', 'start': 0.0, 'duration': 1.0},
            {'text': 'AAAA',           'start': 1.0, 'duration': 1.0},
            {'text': 'BBBB',           'start': 2.0, 'duration': 1.0},
        ])

    def test_ellipsis(self):
        result = split_into_sentences([
            {
                'text':     'Hello... World',
                'start':    0.0,
                'duration': 1.0,
            },
        ])
        self.assertEqual(result, [
            {'text': 'Hello...', 'start': 0.0, 'duration': 0.6153846153846154},
            {'text': 'World',    'start': 0.6153846153846154, 'duration': 0.38461538461538464},
        ])

    # ── Ready? Ready. Here we go. ─────────────────────────────────────────

    def test_ready_split_produces_two_captions(self):
        result = split_multi_speaker_captions([
            {'text': '-Ready?\n-Ready. Here we go.', 'start': 1796.794, 'duration': 1.735},
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['text'], 'Ready?')
        self.assertEqual(result[1]['text'], 'Ready. Here we go.')

    def test_ready_split_timecodes(self):
        result = split_multi_speaker_captions([
            {'text': '-Ready?\n-Ready. Here we go.', 'start': 1796.794, 'duration': 1.735},
        ])
        self.assertAlmostEqual(result[0]['start'], 1796.794, places=3)
        self.assertAlmostEqual(result[0]['duration'] + result[1]['duration'], 1.735, places=3)
        self.assertAlmostEqual(result[1]['start'], result[0]['start'] + result[0]['duration'], places=3)

    def test_ready_full_pipeline_produces_three_captions(self):
        after_multi     = split_multi_speaker_captions([
            {'text': '-Ready?\n-Ready. Here we go.', 'start': 1796.794, 'duration': 1.735},
        ])
        after_sentences = split_into_sentences(after_multi)
        self.assertEqual(len(after_sentences), 3)
        self.assertEqual([c['text'] for c in after_sentences], ['Ready?', 'Ready.', 'Here we go.'])

    def test_ready_full_pipeline_timecodes_are_contiguous(self):
        after_multi     = split_multi_speaker_captions([
            {'text': '-Ready?\n-Ready. Here we go.', 'start': 1796.794, 'duration': 1.735},
        ])
        after_sentences = split_into_sentences(after_multi)
        self.assertAlmostEqual(sum(c['duration'] for c in after_sentences), 1.735, places=3)
        for i in range(1, len(after_sentences)):
            self.assertAlmostEqual(
                after_sentences[i]['start'],
                after_sentences[i-1]['start'] + after_sentences[i-1]['duration'],
                places=3,
            )


class TestThreeSpeakers(unittest.TestCase):
    """Three-speaker caption: '-[Alex] 49.\n-Pork.\n-[Alex] 59.'
    Parts: '[Alex] 49.' (10), 'Pork.' (5), '[Alex] 59.' (10) → total 25
    With duration=2.5: durations are 1.0, 0.5, 1.0"""

    INPUT = {
        'text':     '-[Alex] 49.\n-Pork.\n-[Alex] 59.',
        'start':    100.0,
        'duration': 2.5,
    }

    def test_produces_three_captions(self):
        result = split_multi_speaker_captions([self.INPUT])
        self.assertEqual(len(result), 3)

    def test_texts(self):
        result = split_multi_speaker_captions([self.INPUT])
        self.assertEqual([c['text'] for c in result], ['[Alex] 49.', 'Pork.', '[Alex] 59.'])

    def test_timecodes(self):
        result = split_multi_speaker_captions([self.INPUT])
        self.assertAlmostEqual(result[0]['start'],    100.0, places=3)
        self.assertAlmostEqual(result[0]['duration'],   1.0, places=3)
        self.assertAlmostEqual(result[1]['start'],    101.0, places=3)
        self.assertAlmostEqual(result[1]['duration'],   0.5, places=3)
        self.assertAlmostEqual(result[2]['start'],    101.5, places=3)
        self.assertAlmostEqual(result[2]['duration'],   1.0, places=3)

    def test_total_duration_preserved(self):
        result = split_multi_speaker_captions([self.INPUT])
        total = sum(c['duration'] for c in result)
        self.assertAlmostEqual(total, 2.5, places=3)



class TestNormalizeSoundeffectPipeline(unittest.TestCase):
    """Integration tests: split_into_sentences → normalize_soundeffect_captions."""

    def test_trailing_caps_after_ellipsis(self):
        caps = [{'text': 'They are Andy Zaltzman... CHEERING AND APPLAUSE', 'start': 0.0, 'duration': 3.0}]
        result = normalize_soundeffect_captions(split_into_sentences(caps))
        self.assertEqual([c['text'] for c in result], ['They are Andy Zaltzman...', '[CHEERING AND APPLAUSE]'])

    def test_sentence_ending_with_repeated_ok(self):
        caps = [{'text': "Right, I'm going inside leg,\noutside leg. OK, OK.", 'start': 0.0, 'duration': 4.0}]
        result = normalize_soundeffect_captions(split_into_sentences(caps))
        self.assertEqual([c['text'] for c in result], ["Right, I'm going inside leg, outside leg.", 'OK, OK.'])

    def test_sentence_split_leaving_standalone_i(self):
        caps = [{'text': "Well, who do you think's going\nto get one point? I...", 'start': 0.0, 'duration': 3.0}]
        result = normalize_soundeffect_captions(split_into_sentences(caps))
        self.assertEqual([c['text'] for c in result], ["Well, who do you think's going to get one point?", 'I...'])

    def test_ok_laughter_split_then_normalized(self):
        # 'OK. LAUGHTER' — sentence splitter separates them; OK stays as speech, LAUGHTER gets bracketed
        caps = [{'text': 'OK. LAUGHTER', 'start': 0.0, 'duration': 2.0}]
        result = normalize_soundeffect_captions(split_into_sentences(caps))
        self.assertEqual([c['text'] for c in result], ['OK.', '[LAUGHTER]'])

    def test_no_space_between_sentences(self):
        # 'God.Yeah' has no whitespace — must still split at the sentence boundary
        caps = [{'text': "HE SIGHS\nOh, God.Yeah, it's in there.", 'start': 0.0, 'duration': 2.0}]
        result = normalize_soundeffect_captions(split_into_sentences(split_multi_speaker_captions(strip_music_markers(caps))))
        self.assertEqual([c['text'] for c in result], ['[HE SIGHS] Oh, God.', "Yeah, it's in there."])

    def test_decimal_not_split(self):
        caps = [{'text': 'I ran 2.5 kilometres.', 'start': 0.0, 'duration': 2.0}]
        result = normalize_soundeffect_captions(split_into_sentences(caps))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], 'I ran 2.5 kilometres.')

    def test_acronym_splits_at_sentence_boundary(self):
        caps = [{'text': 'I was born in the U.S.A. Then I moved.', 'start': 0.0, 'duration': 2.0}]
        result = split_into_sentences(caps)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['text'], 'I was born in the U.S.A.')
        self.assertEqual(result[1]['text'], 'Then I moved.')

    def test_leading_dots_not_split(self):
        # Leading dots before a name must not cause a spurious split
        caps = [{'text': '..Babatunde Aleshe...\nCHEERING AND APPLAUSE', 'start': 0.0, 'duration': 3.0}]
        result = normalize_soundeffect_captions(split_into_sentences(split_multi_speaker_captions(strip_music_markers(caps))))
        self.assertEqual([c['text'] for c in result], ['..Babatunde Aleshe...', '[CHEERING AND APPLAUSE]'])

    def test_acronym_splits_at_sentence_boundary_no_space(self):
        caps = [{'text': 'I was born in the U.S.A.Then I moved.', 'start': 0.0, 'duration': 2.0}]
        result = split_into_sentences(caps)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['text'], 'I was born in the U.S.A.')
        self.assertEqual(result[1]['text'], 'Then I moved.')

    def test_all_caps_word_no_space_split(self):
        # "I'm a comedian.OK." — no whitespace between sentences, second sentence is all-caps
        caps = [{'text': "I'm a comedian.OK.", 'start': 0.0, 'duration': 2.0}]
        result = split_into_sentences(caps)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['text'], "I'm a comedian.")
        self.assertEqual(result[1]['text'], 'OK.')

    def test_contraction_after_question_mark_no_space(self):
        # "You all right?I'm good." — no whitespace, next sentence starts with contraction
        caps = [{'text': "You all right?I'm good.", 'start': 0.0, 'duration': 2.0}]
        result = split_into_sentences(caps)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['text'], 'You all right?')
        self.assertEqual(result[1]['text'], "I'm good.")


class TestNormalizeSoundeffectCaptions(unittest.TestCase):

    def _cap(self, text):
        return {'text': text, 'start': 0.0, 'duration': 1.0}

    def test_all_caps_gets_bracketed(self):
        result = normalize_soundeffect_captions([self._cap('LAUGHTER')])
        self.assertEqual(result[0]['text'], '[LAUGHTER]')

    def test_multi_word_all_caps_gets_bracketed(self):
        result = normalize_soundeffect_captions([self._cap('LAUGHTER CHEERING AND APPLAUSE')])
        self.assertEqual(result[0]['text'], '[LAUGHTER CHEERING AND APPLAUSE]')

    def test_already_bracketed_unchanged(self):
        result = normalize_soundeffect_captions([self._cap('[LAUGHTER]')])
        self.assertEqual(result[0]['text'], '[LAUGHTER]')

    def test_mixed_case_unchanged(self):
        result = normalize_soundeffect_captions([self._cap('Hello there.')])
        self.assertEqual(result[0]['text'], 'Hello there.')

    def test_single_letter_prefix_i_unchanged(self):
        result = normalize_soundeffect_captions([self._cap("I mean, you're useless at this.")])
        self.assertEqual(result[0]['text'], "I mean, you're useless at this.")

    def test_mixed_case_rest_gets_prefix_bracketed(self):
        result = normalize_soundeffect_captions([self._cap('HELLO there.')])
        self.assertEqual(result[0]['text'], '[HELLO] there.')

    def test_other_fields_preserved(self):
        cap = {'text': 'APPLAUSE', 'start': 5.0, 'duration': 2.0, 'speaker': 'Other'}
        result = normalize_soundeffect_captions([cap])
        self.assertEqual(result[0], {'text': '[APPLAUSE]', 'start': 5.0, 'duration': 2.0, 'speaker': 'Other'})

    def test_original_caption_not_mutated(self):
        cap = {'text': 'APPLAUSE', 'start': 0.0, 'duration': 1.0}
        normalize_soundeffect_captions([cap])
        self.assertEqual(cap['text'], 'APPLAUSE')

    def test_empty_list(self):
        self.assertEqual(normalize_soundeffect_captions([]), [])

    def test_mixed_list(self):
        caps = [self._cap('Hello.'), self._cap('APPLAUSE'), self._cap('[LAUGHTER]')]
        result = normalize_soundeffect_captions(caps)
        self.assertEqual([c['text'] for c in result], ['Hello.', '[APPLAUSE]', '[LAUGHTER]'])

    def test_caps_prefix_colon_with_mixed_case_speech(self):
        result = normalize_soundeffect_captions([self._cap('TINNY VOICE: Hello, Greggy.')])
        self.assertEqual(result[0]['text'], '[TINNY VOICE]: Hello, Greggy.')

    def test_caps_prefix_no_colon_single_word(self):
        result = normalize_soundeffect_captions([self._cap('GREG Oh, interesting.')])
        self.assertEqual(result[0]['text'], '[GREG] Oh, interesting.')

    def test_caps_prefix_no_colon_multi_word(self):
        result = normalize_soundeffect_captions([self._cap('WHISTLE BLOWS Not bad.')])
        self.assertEqual(result[0]['text'], '[WHISTLE BLOWS] Not bad.')

    def test_caps_prefix_hyphenated(self):
        result = normalize_soundeffect_captions([self._cap("HIGH-PITCHED: I'll give you a clue!")])
        self.assertEqual(result[0]['text'], "[HIGH-PITCHED]: I'll give you a clue!")

    def test_standalone_ok_unchanged(self):
        result = normalize_soundeffect_captions([self._cap('OK.')])
        self.assertEqual(result[0]['text'], 'OK.')

    def test_standalone_okay_unchanged(self):
        result = normalize_soundeffect_captions([self._cap('OKAY.')])
        self.assertEqual(result[0]['text'], 'OKAY.')

    def test_repeated_ok_unchanged(self):
        result = normalize_soundeffect_captions([self._cap('OK, OK.')])
        self.assertEqual(result[0]['text'], 'OK, OK.')

    def test_ok_prefix_before_speech_unchanged(self):
        result = normalize_soundeffect_captions([self._cap('OK thanks.')])
        self.assertEqual(result[0]['text'], 'OK thanks.')

    def test_caps_prefix_ok_exception(self):
        result = normalize_soundeffect_captions([self._cap('ROSIE: OK.')])
        self.assertEqual(result[0]['text'], '[ROSIE]: OK.')

    def test_caps_prefix_okay_exception(self):
        result = normalize_soundeffect_captions([self._cap('ROSIE: OKAY.')])
        self.assertEqual(result[0]['text'], '[ROSIE]: OKAY.')

    def test_caps_prefix_all_caps_rest_fully_bracketed(self):
        # rest is all-caps and not OK/OKAY → full-bracket fallback
        result = normalize_soundeffect_captions([self._cap('ROSIE: CHEERING')])
        self.assertEqual(result[0]['text'], '[ROSIE: CHEERING]')

    # ── Name + action patterns ────────────────────────────────────────────

    def test_name_plus_action(self):
        result = normalize_soundeffect_captions([self._cap('SHE SCREAMS')])
        self.assertEqual(result[0]['text'], '[SHE SCREAMS]')

    def test_name_plus_multi_action(self):
        result = normalize_soundeffect_captions([self._cap('EMMA GASPS LAUGHTER')])
        self.assertEqual(result[0]['text'], '[EMMA GASPS LAUGHTER]')

    # ── All-caps with commas ──────────────────────────────────────────────

    def test_all_caps_with_commas(self):
        result = normalize_soundeffect_captions([self._cap('AUDIENCE GROANS, CHEERS, APPLAUDS')])
        self.assertEqual(result[0]['text'], '[AUDIENCE GROANS, CHEERS, APPLAUDS]')

    def test_all_caps_two_words_with_comma(self):
        result = normalize_soundeffect_captions([self._cap('LAUGHTER, APPLAUSE')])
        self.assertEqual(result[0]['text'], '[LAUGHTER, APPLAUSE]')

    # ── Single letters / spelled-out words — not bracketed ───────────────
    # No sequence of 2+ consecutive uppercase letters, so the all-caps rule
    # doesn't fire. These are speech, not sound effects.

    def test_single_letter_e(self):
        result = normalize_soundeffect_captions([self._cap('E.')])
        self.assertEqual(result[0]['text'], 'E.')

    def test_single_letter_a(self):
        result = normalize_soundeffect_captions([self._cap('A.')])
        self.assertEqual(result[0]['text'], 'A.')

    def test_spelled_out_letters_with_commas(self):
        result = normalize_soundeffect_captions([self._cap('S, T, I.')])
        self.assertEqual(result[0]['text'], 'S, T, I.')

    def test_spelled_out_word_with_hyphens(self):
        result = normalize_soundeffect_captions([self._cap('S-E-A.')])
        self.assertEqual(result[0]['text'], 'S-E-A.')

    def test_single_letter_i_with_ellipsis(self):
        result = normalize_soundeffect_captions([self._cap('I...')])
        self.assertEqual(result[0]['text'], 'I...')


if __name__ == '__main__':
    unittest.main()
