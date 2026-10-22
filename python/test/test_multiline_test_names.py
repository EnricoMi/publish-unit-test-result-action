import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from publish import SomeTestChanges, chunk_test_list, create_tests_list_annotation, \
    get_test_list_annotation, get_test_changes_list_md, get_all_tests_list_annotation, \
    get_skipped_tests_list_annotation, get_all_tests_list, get_skipped_tests_list
from publish.junit import parse_junit_xml_files, process_junit_xml_elems
from publish.publisher import Publisher
from publish.unittestresults import get_test_results


class MultilineTestNamesTest(unittest.TestCase):
    @staticmethod
    def read(annotations):
        # Exercise the serialized annotation boundary, not the writer's in-memory values.
        wire = [SimpleNamespace(**json.loads(json.dumps(annotation.to_dict()))) for annotation in annotations]
        return Publisher.get_test_lists_from_check_run(
            SimpleNamespace(get_annotations=lambda: wire))

    def test_identical_multiline_and_literal_backslash_names_have_no_changes(self):
        names = ['ReplyMatcherTests - Phrase("Jerry?! \r\n NO", True)',
                 r'ReplyMatcherTests - Phrase("Jerry?! \r\n NO", True)']
        names += ['ordinary test %03d' % i for i in range(151)]
        before, skipped = self.read(get_test_list_annotation(names, 'test'))
        self.assertEqual(sorted(names), before)
        self.assertIsNone(skipped)
        changes = SomeTestChanges(before, names, None, None)
        self.assertFalse(changes.has_changes)
        self.assertEqual(set(), changes.adds())
        self.assertEqual(set(), changes.removes())

    def test_line_break_variants_round_trip_in_both_categories(self):
        for name in ['before\nafter', 'before\rafter', 'before\r\nafter',
                     '\nleading', 'trailing\n', '\n', '雪\n☃']:
            with self.subTest(name=name):
                annotations = get_test_list_annotation([name], 'test')
                annotations += get_test_list_annotation([name], 'skipped test')
                self.assertEqual(([name], [name]), self.read(annotations))

    def test_ordinary_annotation_bytes_and_json_looking_names_are_unchanged(self):
        names = [r'literal\n', '"quoted"', '["array"]', 'plain']
        annotation, = get_test_list_annotation(names, 'test')
        self.assertEqual('4 tests found', annotation.title)
        self.assertEqual('There are 4 tests, see "Raw output" for the full list of tests.', annotation.message)
        self.assertEqual('\n'.join(sorted(names)), annotation.raw_details)
        self.assertEqual((sorted(names), None), self.read([annotation]))

    def test_marked_annotations_are_not_misread_by_legacy_title_filter(self):
        annotation, = get_test_list_annotation(['a\nb'], 'test')
        legacy_title = re.compile(r'^\d+ test(s)? found( \(test \d+ to \d+\))?$')
        self.assertIsNone(legacy_title.match(annotation.title))

    def test_encoding_expansion_is_counted_before_chunking(self):
        names = ['雪\n' * 3, 'quote"\n' * 2, r'literal\n', 'ordinary']
        annotations = get_test_list_annotation(names, 'test', max_chunk_size=32)
        self.assertGreater(len(annotations), 1)
        for annotation in annotations:
            self.assertLessEqual(len(annotation.to_dict()['raw_details'].encode('utf8')), 32)
            for line in annotation.raw_details.split('\n'):
                self.assertIsInstance(json.loads(line), str)
        self.assertEqual((sorted(names), None), self.read(annotations))

    def test_oversize_encoded_name_disables_whole_list(self):
        self.assertEqual([], get_test_list_annotation(['\n' * 10, 'short'], 'test', max_chunk_size=16))

    def test_exact_limit_chunk_makes_progress(self):
        self.assertEqual([['abc'], ['x']], chunk_test_list(['abc', 'x'], '\n', 4))

    def test_corrupted_legacy_name_disables_comparison(self):
        annotation = create_tests_list_annotation(
            '1 test found', 'There is 1 test, see "Raw output" for the name of the test.',
            'one\nmultiline test')
        before, _ = self.read([annotation])
        self.assertIsNone(before)
        self.assertFalse(SomeTestChanges(before, ['one\nmultiline test'], None, None).has_changes)

    def test_invalid_chunk_does_not_produce_partial_list(self):
        annotations = [create_tests_list_annotation(
            f'2 tests found (test {i} to {i})',
            f'There are 2 tests, see "Raw output" for the list of tests {i} to {i}.', raw)
            for i, raw in [(1, 'ordinary'), (2, 'broken\nname')]]
        annotations += get_test_list_annotation(['skipped control'], 'skipped test')
        self.assertEqual((None, ['skipped control']), self.read(annotations))

    def test_malformed_marked_data_is_not_treated_as_legacy(self):
        annotation, = get_test_list_annotation(['a\nb'], 'test')
        for raw in ['not json', '123', 'null', '["array"]', '"ok"\n"extra"']:
            with self.subTest(raw=raw):
                damaged = create_tests_list_annotation(annotation.title, annotation.message, raw)
                self.assertEqual((None, None), self.read([damaged]))

    def test_real_changes_remain_distinct_from_display_escaping(self):
        before, _ = self.read(get_test_list_annotation(['a\nb', r'a\nb'], 'test'))
        changes = SomeTestChanges(before, [r'a\nb', 'new\rname'], None, None)
        self.assertEqual({'a\nb'}, changes.removes())
        self.assertEqual({'new\rname'}, changes.adds())

    def test_markdown_escapes_line_breaks_without_terminating_fence(self):
        markdown = get_test_changes_list_md(['line\r\n```\nend', r'literal\n', '````'], None)
        self.assertEqual('`````\nline\\r\\n```\\nend\nliteral\\n\n````\n`````\n', markdown)
        self.assertNotIn('\r', markdown)

    def test_markdown_ordinary_names_and_limit_are_unchanged(self):
        self.assertEqual('```\none\n…\n```\n', get_test_changes_list_md(['one', 'two'], 1))

    def test_identical_junit_xml_reports_preserve_all_and_skipped_identities(self):
        names = ['Phrase("Jerry?! \r\n NO", True)', r'Phrase("Jerry?! \r\n NO", True)']
        names += ['ordinary test %03d' % i for i in range(151)]
        suite = ET.Element('testsuite', name='synthetic', tests='153', skipped='1')
        for index, name in enumerate(names):
            case = ET.SubElement(suite, 'testcase', classname='ReplyMatcherTests', name=name)
            if index == 0:
                ET.SubElement(case, 'skipped')
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'results.xml'
            ET.ElementTree(suite).write(report, encoding='utf8')
            parsed = process_junit_xml_elems(parse_junit_xml_files([str(report)], False, False))
        self.assertEqual([], parsed.errors)
        results = get_test_results(parsed.with_commit('synthetic'), False)
        self.assertEqual(153, results.tests)
        cases = results.case_results
        annotations = get_all_tests_list_annotation(cases) + get_skipped_tests_list_annotation(cases)
        all_before, skipped_before = self.read(annotations)
        all_current, skipped_current = get_all_tests_list(cases), get_skipped_tests_list(cases)
        self.assertEqual(sorted(all_current), all_before)
        self.assertEqual(skipped_current, skipped_before)
        changes = SomeTestChanges(all_before, all_current, skipped_before, skipped_current)
        self.assertFalse(changes.has_changes)
        self.assertEqual(set(), changes.skips())
        self.assertEqual(set(), changes.un_skips())
        # An actual state change remains visible, without changing test identity.
        changed = SomeTestChanges(all_before, all_current, skipped_before, [])
        self.assertEqual(set(skipped_current), changed.un_skips())
        self.assertEqual(set(), changed.adds())
        self.assertEqual(set(), changed.removes())


if __name__ == '__main__':
    unittest.main()
