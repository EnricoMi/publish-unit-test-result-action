import base64
import gzip
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Any, Union, Optional, Tuple, Mapping, Iterator, Set, Iterable

from publish.unittestresults import Numeric, UnitTestCaseResults, UnitTestRunResults, \
    UnitTestRunDeltaResults, UnitTestRunResultsOrDeltaResults, ParseError

logger = logging.getLogger('publish')
digest_prefix = '[test-results]:data:'
digest_mime_type = 'application/gzip'
digest_encoding = 'base64'
digest_header = f'{digest_prefix}{digest_mime_type};{digest_encoding},'
digit_space = '  '
punctuation_space = ' '

comment_mode_off = 'off'
comment_mode_create = 'create new'
comment_mode_update = 'update last'
comment_modes = [
    comment_mode_off,
    comment_mode_create,
    comment_mode_update
]

fail_on_mode_nothing = 'nothing'
fail_on_mode_errors = 'errors'
fail_on_mode_failures = 'test failures'
fail_on_modes = [
    fail_on_mode_nothing,
    fail_on_mode_errors,
    fail_on_mode_failures
]

hide_comments_mode_off = 'off'
hide_comments_mode_all_but_latest = 'all but latest'
hide_comments_mode_orphaned = 'orphaned commits'
hide_comments_modes = [
    hide_comments_mode_off,
    hide_comments_mode_all_but_latest,
    hide_comments_mode_orphaned
]

pull_request_build_mode_commit = 'commit'
pull_request_build_mode_merge = 'merge'
pull_request_build_modes = [
    pull_request_build_mode_commit,
    pull_request_build_mode_merge
]

all_tests_list = 'all tests'
skipped_tests_list = 'skipped tests'
none_list = 'none'
available_annotations = [all_tests_list, skipped_tests_list, none_list]
default_annotations = [all_tests_list, skipped_tests_list]


class CaseMessages(defaultdict):
    def __init__(self, items=None):
        if items is None:
            items = []
        super(CaseMessages, self).__init__(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))),
            items
        )


class SomeTestChanges:
    def __init__(self,
                 all_tests_before: Optional[List[str]],
                 all_tests_current: Optional[List[str]],
                 skipped_tests_before: Optional[List[str]],
                 skipped_tests_current: Optional[List[str]]):
        self._all_tests_before = set(all_tests_before) if all_tests_before is not None else None
        self._all_tests_current = set(all_tests_current) if all_tests_current is not None else None
        self._skipped_tests_before = set(skipped_tests_before) if skipped_tests_before is not None else None
        self._skipped_tests_current = set(skipped_tests_current) if skipped_tests_current is not None else None

    def adds(self) -> Optional[Set[str]]:
        if self._all_tests_before is None or self._all_tests_current is None:
            return None
        return self._all_tests_current - self._all_tests_before

    def removes(self) -> Optional[Set[str]]:
        if self._all_tests_before is None or self._all_tests_current is None:
            return None
        return self._all_tests_before - self._all_tests_current

    def remains(self) -> Optional[Set[str]]:
        if self._all_tests_before is None or self._all_tests_current is None:
            return None
        return self._all_tests_before.intersection(self._all_tests_current)

    def skips(self) -> Optional[Set[str]]:
        if self._skipped_tests_before is None or self._skipped_tests_current is None:
            return None
        return self._skipped_tests_current - self._skipped_tests_before

    def un_skips(self) -> Optional[Set[str]]:
        if self._skipped_tests_before is None or self._skipped_tests_current is None:
            return None
        return self._skipped_tests_before - self._skipped_tests_current

    def added_and_skipped(self) -> Optional[Set[str]]:
        added = self.adds()
        skipped = self.skips()
        if added is None or skipped is None:
            return None
        return added.intersection(skipped)

    def remaining_and_skipped(self) -> Optional[Set[str]]:
        remaining = self.remains()
        skipped = self.skips()
        if remaining is None or skipped is None:
            return None
        return remaining.intersection(skipped)

    def remaining_and_un_skipped(self) -> Optional[Set[str]]:
        remaining = self.remains()
        un_skipped = self.un_skips()
        if remaining is None or un_skipped is None:
            return None
        return remaining.intersection(un_skipped)

    def removed_skips(self) -> Optional[Set[str]]:
        removed = self.removes()
        skipped_before = self._skipped_tests_before
        if removed is None or skipped_before is None:
            return None
        return skipped_before.intersection(removed)


def utf8_character_length(c: int) -> int:
    if c >= 0x00010000:
        return 4
    if c >= 0x00000800:
        return 3
    if c >= 0x00000080:
        return 2
    return 1


def alternating_range(positive_first: bool = True) -> Iterator[int]:
    i = 0
    yield i

    if positive_first:
        while True:
            i += 1
            yield i
            yield -i
    else:
        while True:
            i += 1
            yield -i
            yield i


def abbreviate_bytes(string: Optional[str], length: int) -> Optional[str]:
    if length < 3:
        raise ValueError(f'Length must at least allow for the replacement character: {length}')

    if string is None:
        return None

    char_length = len(string)
    byte_length = len(string.encode('utf8'))
    if byte_length <= length:
        return string

    odd = char_length % 2
    middle = char_length // 2
    pre = middle
    suf = char_length - middle
    for index in alternating_range(odd == 1):
        if index >= 0:
            suf -= 1
        else:
            pre -= 1
        byte_length -= utf8_character_length(ord(string[middle + index]))
        if byte_length <= length - 3:
            return string[:pre] + '…' + (string[-suf:] if suf else '')


def abbreviate(string: Optional[str], length: int) -> Optional[str]:
    if length < 1:
        raise ValueError(f'Length must at least allow for the replacement character: {length}')

    if string is None:
        return None

    char_length = len(string)
    if char_length <= length:
        return string

    pre = length // 2
    suf = (length - 1) // 2
    return string[:pre] + '…' + (string[-suf:] if suf else '')


def get_formatted_digits(*numbers: Union[Optional[int], Numeric]) -> Tuple[int, int]:
    if isinstance(numbers[0], dict):
        # TODO: is not None else None?!?
        number_digits = max([len(as_stat_number(abs(number.get('number')) if number.get('number') is not None else None))
                             for number in numbers])
        delta_digits = max([len(as_stat_number(abs(number.get('delta')) if number.get('delta') is not None else None))
                            for number in numbers])
        return number_digits, delta_digits
    return max([len(as_stat_number(abs(number) if number is not None else None))
                for number in numbers]), 0


def get_magnitude(value: Union[int, dict]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        if 'number' in value:
            return value.get('number')
        if 'duration' in value:
            return value.get('duration')
    return None


def get_delta(value: Optional[Union[int, Numeric]]) -> Optional[int]:
    if isinstance(value, int):
        return None
    if isinstance(value, Mapping):  # Numeric
        return value.get('delta')
    return None


def as_short_commit(commit: Optional[str]) -> str:
    return commit[0:8] if commit else None


def as_delta(number: int, digits: int) -> str:
    string = as_stat_number(abs(number), digits)
    if number == 0:
        sign = '±'
    elif number > 0:
        sign = '+'
    else:
        sign = ' - '
    return f'{sign}{string}'


def as_stat_number(number: Optional[Union[int, Numeric]],
                   number_digits: int = 0,
                   delta_digits: int = 0,
                   label: str = None) -> str:
    if number is None:
        if label:
            return 'N/A {}'.format(label)
        return 'N/A'
    if isinstance(number, int):
        formatted = '{number:0{digits},}'.format(number=number, digits=number_digits)
        res = re.search('[^0,]', formatted)
        pos = res.start() if res else len(formatted)-1
        formatted = '{}{}'.format(formatted[:pos].replace('0', digit_space), formatted[pos:])
        formatted = formatted.replace(',', punctuation_space)
        if label:
            return '{} {}'.format(formatted, label)
        return formatted
    elif isinstance(number, dict):
        extra_fields = [
            as_delta(number['delta'], delta_digits) if 'delta' in number else '',
            as_stat_number(number['new'], 0, 0, 'new') if 'new' in number else '',
            as_stat_number(number['gone'], 0, 0, 'gone') if 'gone' in number else '',
        ]
        extra = ', '.join([field for field in extra_fields if field != ''])

        return ''.join([
            as_stat_number(number.get('number'), number_digits, delta_digits, label),
            f' {extra} ' if extra != '' else ''
        ])
    else:
        logger.warning(f'unsupported stats number type {type(number)}: {number}')
        return 'N/A'


def as_stat_duration(duration: Optional[Union[int, Numeric]], label=None) -> str:
    if duration is None:
        if label:
            return f'N/A {label}'
        return 'N/A'
    if isinstance(duration, float):
        duration = int(duration)
    if isinstance(duration, int):
        duration = abs(duration)
        strings = []
        for unit in ['s', 'm', 'h']:
            if unit == 's' or duration:
                strings.insert(0, f'{duration % 60}{unit}')
                duration //= 60
        string = ' '.join(strings)
        if label:
            return f'{string} {label}'
        return string
    elif isinstance(duration, dict):
        delta = duration.get('delta')
        duration = duration.get('duration')
        sign = '' if delta is None else '±' if delta == 0 else '+' if delta > 1 else '-'
        if delta and abs(delta) >= 60:
            sign += ' '
        return as_stat_duration(duration, label) + (f' {sign}{as_stat_duration(delta)}' if delta is not None else '')
    else:
        logger.warning(f'unsupported stats duration type {type(duration)}: {duration}')
        return 'N/A'


def digest_string(string: str) -> str:
    return str(base64.encodebytes(gzip.compress(bytes(string, 'utf8'), compresslevel=9)), 'utf8') \
        .replace('\n', '')


def ungest_string(string: str) -> str:
    return str(gzip.decompress(base64.decodebytes(bytes(string, 'utf8'))), 'utf8')


def get_digest_from_stats(stats: UnitTestRunResults) -> str:
    d = stats.to_dict()
    del d['errors']  # we don't need errors in the digest
    return digest_string(json.dumps(d))


def get_stats_from_digest(digest: str) -> UnitTestRunResults:
    return UnitTestRunResults.from_dict(json.loads(ungest_string(digest)))


def get_short_summary(stats: UnitTestRunResults) -> str:
    """Provides a single-line summary for the given stats."""
    perrors = len(stats.errors)
    tests = get_magnitude(stats.tests)
    success = get_magnitude(stats.tests_succ)
    skipped = get_magnitude(stats.tests_skip)
    failure = get_magnitude(stats.tests_fail)
    error = get_magnitude(stats.tests_error)
    duration = get_magnitude(stats.duration)

    def get_test_summary():
        if tests == 0:
            if perrors == 0:
                return 'No tests found'
            else:
                return f'{perrors} parse errors'
        if tests > 0:
            if (failure is None or failure == 0) and \
                    (error is None or error == 0) and perrors == 0:
                if skipped == 0 and success == tests:
                    return 'All {} pass'.format(as_stat_number(tests, 0, 0, 'tests'))
                if skipped > 0 and success == tests - skipped:
                    return 'All {} pass, {}'.format(
                        as_stat_number(success, 0, 0, 'tests'),
                        as_stat_number(skipped, 0, 0, 'skipped')
                    )

            summary = [as_stat_number(number, 0, 0, label)
                       for number, label in [(perrors, 'parse errors'),
                                             (error, 'errors'), (failure, 'fail'),
                                             (skipped, 'skipped'), (success, 'pass')]
                       if number > 0]
            summary = ', '.join(summary)

            # when all except tests are None or 0
            if len(summary) == 0:
                return f'{as_stat_number(tests, 0, 0, "tests")} found'
            return summary

    if tests is None or tests == 0 or duration is None:
        return get_test_summary()

    return f'{get_test_summary()} in {as_stat_duration(duration)}'


def get_link_and_tooltip_label_md(label: str, tooltip: str) -> str:
    return '[{label}]({link} "{tooltip}")'.format(
        label=label,
        # bump the version if you change the target of this link (if it did not exist already) or change the section
        link='https://github.com/EnricoMi/publish-unit-test-result-action/blob/v1.20/README.md#the-symbols',
        tooltip=tooltip
    )


all_tests_label_md = 'tests'
passed_tests_label_md = get_link_and_tooltip_label_md(':heavy_check_mark:', 'passed tests')
skipped_tests_label_md = get_link_and_tooltip_label_md(':zzz:', 'skipped / disabled tests')
failed_tests_label_md = get_link_and_tooltip_label_md(':x:', 'failed tests')
test_errors_label_md = get_link_and_tooltip_label_md(':fire:', 'test errors')
duration_label_md = get_link_and_tooltip_label_md(':stopwatch:', 'duration of all tests')


def get_short_summary_md(stats: UnitTestRunResultsOrDeltaResults) -> str:
    """Provides a single-line summary with markdown for the given stats."""
    md = ('{tests} {tests_succ} {tests_skip} {tests_fail} {tests_error}'.format(
        tests=as_stat_number(stats.tests, 0, 0, all_tests_label_md),
        tests_succ=as_stat_number(stats.tests_succ, 0, 0, passed_tests_label_md),
        tests_skip=as_stat_number(stats.tests_skip, 0, 0, skipped_tests_label_md),
        tests_fail=as_stat_number(stats.tests_fail, 0, 0, failed_tests_label_md),
        tests_error=as_stat_number(stats.tests_error, 0, 0, test_errors_label_md),
    ))
    return md


def get_test_changes_summary_md(changes: Optional[SomeTestChanges], list_limit: Optional[int]) -> str:
    if not changes or list_limit == 0:
        return ''

    test_changes_details = []
    if changes.removes():
        if changes.adds():
            test_changes_details.append(
                get_test_changes_md(
                    'This pull request <b>removes</b> {} and <b>adds</b> {} tests. '
                    '<i>Note that renamed tests count towards both.</i>'.format(
                        len(changes.removes()),
                        len(changes.adds()),
                    ),
                    list_limit,
                    changes.removes(),
                    changes.adds()
                )
            )
        else:
            test_changes_details.append(
                get_test_changes_md(
                    'This pull request <b>removes</b> {} test{}.'.format(
                        len(changes.removes()),
                        's' if len(changes.removes()) > 1 else ''
                    ),
                    list_limit,
                    list(changes.removes())
                )
            )

    if changes.removed_skips() and changes.added_and_skipped():
        test_changes_details.append(
            get_test_changes_md(
                'This pull request <b>removes</b> {} skipped test{} and <b>adds</b> {} skipped test{}. '
                '<i>Note that renamed tests count towards both.</i>'.format(
                    len(changes.removed_skips()),
                    's' if len(changes.removed_skips()) > 1 else '',
                    len(changes.added_and_skipped()),
                    's' if len(changes.added_and_skipped()) > 1 else ''
                ),
                list_limit,
                changes.removed_skips(),
                changes.added_and_skipped()
            )
        )

    if changes.remaining_and_skipped():
        if changes.remaining_and_un_skipped():
            test_changes_details.append(
                get_test_changes_md(
                    'This pull request <b>skips</b> {} and <b>un-skips</b> {} tests.'.format(
                        len(changes.remaining_and_skipped()),
                        len(changes.remaining_and_un_skipped())
                    ),
                    list_limit,
                    changes.remaining_and_skipped(),
                    changes.remaining_and_un_skipped()
                )
            )
        else:
            test_changes_details.append(
                get_test_changes_md(
                    'This pull request <b>skips</b> {} test{}.'.format(
                        len(changes.remaining_and_skipped()),
                        's' if len(changes.remaining_and_skipped()) > 1 else ''
                    ),
                    list_limit,
                    changes.remaining_and_skipped()
                )
            )

    return '\n'.join(test_changes_details)


def get_test_changes_md(summary: str, list_limit: Optional[int], *tests: Iterable[str]) -> str:
    tests = '\n'.join([get_test_changes_list_md(sorted(test), list_limit) for test in tests])
    return (
        f'<details>\n'
        f'  <summary>{summary}</summary>\n'
        f'\n'
        f'{tests}'
        f'</details>\n'
    )


def get_test_changes_list_md(tests: List[str], limit: Optional[int]) -> str:
    if limit:
        tests = tests[:limit] + (['…'] if len(tests) > limit else [])
    tests = '\n'.join(tests)
    return f'```\n{tests}\n```\n'


def get_long_summary_md(stats: UnitTestRunResultsOrDeltaResults,
                        details_url: Optional[str] = None,
                        test_changes: Optional[SomeTestChanges] = None,
                        test_list_changes_limit: Optional[int] = None) -> str:
    """Provides a long summary in Markdown notation for the given stats."""
    hide_runs = stats.runs == stats.tests and \
                stats.runs_succ == stats.tests_succ and \
                stats.runs_skip == stats.tests_skip and \
                stats.runs_fail == stats.tests_fail and \
                stats.runs_error == stats.tests_error

    files_digits, files_delta_digits = get_formatted_digits(stats.files, stats.tests, stats.runs)
    success_digits, success_delta_digits = get_formatted_digits(stats.suites, stats.tests_succ, stats.runs_succ)
    skip_digits, skip_delta_digits = get_formatted_digits(stats.tests_skip, stats.runs_skip)
    fail_digits, fail_delta_digits = get_formatted_digits(stats.tests_fail, stats.runs_fail)
    error_digits, error_delta_digits = get_formatted_digits(stats.tests_error, stats.runs_error)

    commit = stats.commit
    is_delta_stats = isinstance(stats, UnitTestRunDeltaResults)
    reference_type = stats.reference_type if is_delta_stats else None
    reference_commit = stats.reference_commit if is_delta_stats else None

    errors = len(stats.errors)
    misc_line = '{files} {errors}{suites}  {duration}\n'.format(
        files=as_stat_number(stats.files, files_digits, files_delta_digits, 'files '),
        errors='{} '.format(as_stat_number(errors, success_digits, 0, 'errors ')) if errors > 0 else '',
        suites=as_stat_number(stats.suites, success_digits if errors == 0 else skip_digits, 0, 'suites '),
        duration=as_stat_duration(stats.duration, duration_label_md)
    )

    tests_error_part = ' {tests_error}'.format(
        tests_error=as_stat_number(stats.tests_error, error_digits, error_delta_digits, test_errors_label_md)
    ) if get_magnitude(stats.tests_error) else ''
    tests_line = '{tests} {tests_succ} {tests_skip} {tests_fail}{tests_error_part}\n'.format(
        tests=as_stat_number(stats.tests, files_digits, files_delta_digits, all_tests_label_md),
        tests_succ=as_stat_number(stats.tests_succ, success_digits, success_delta_digits, passed_tests_label_md),
        tests_skip=as_stat_number(stats.tests_skip, skip_digits, skip_delta_digits, skipped_tests_label_md),
        tests_fail=as_stat_number(stats.tests_fail, fail_digits, fail_delta_digits, failed_tests_label_md),
        tests_error_part=tests_error_part
    )

    runs_error_part = ' {runs_error}'.format(
        runs_error=as_stat_number(stats.runs_error, error_digits, error_delta_digits, test_errors_label_md)
    ) if get_magnitude(stats.runs_error) else ''
    runs_line = '{runs} {runs_succ} {runs_skip} {runs_fail}{runs_error_part}\n'.format(
        runs=as_stat_number(stats.runs, files_digits, files_delta_digits, 'runs '),
        runs_succ=as_stat_number(stats.runs_succ, success_digits, success_delta_digits, passed_tests_label_md),
        runs_skip=as_stat_number(stats.runs_skip, skip_digits, skip_delta_digits, skipped_tests_label_md),
        runs_fail=as_stat_number(stats.runs_fail, fail_digits, fail_delta_digits, failed_tests_label_md),
        runs_error_part=runs_error_part,
    )

    details_on = (['parsing errors'] if errors > 0 else []) + \
                 (['failures'] if get_magnitude(stats.tests_fail) > 0 else []) + \
                 (['errors'] if get_magnitude(stats.tests_error) > 0 else [])
    details_on = details_on[0:-2] + [' and '.join(details_on[-2:])] if details_on else []

    details_line = '\nFor more details on these {details_on}, see [this check]({url}).\n'.format(
        details_on=', '.join(details_on),
        url=details_url
    )

    test_changes_details = get_test_changes_summary_md(test_changes, test_list_changes_limit)
    test_changes_details = ('\n' + test_changes_details) if stats.tests and test_changes_details else ''

    commit_line = '\nResults for commit {commit}.{compare}\n'.format(
        commit=as_short_commit(commit),
        compare=' ± Comparison against {reference_type} commit {reference_commit}.'.format(
            reference_type=reference_type,
            reference_commit=as_short_commit(reference_commit)
        ) if reference_type and reference_commit else ''
    )

    return '{misc}{tests}{runs}{details}{commit}{test_changes_details}'.format(
        misc=misc_line,
        tests=tests_line,
        runs=runs_line if not hide_runs else '',
        details=details_line if details_url and details_on else '',
        commit=commit_line,
        test_changes_details=test_changes_details
    )


def get_long_summary_with_digest_md(stats: UnitTestRunResultsOrDeltaResults,
                                    digest_stats: Optional[UnitTestRunResults] = None) -> str:
    """
    Provides the summary of stats with digest of digest_stats if given, otherwise
    digest of stats. In that case, stats must be UnitTestRunResults.

    :param stats: stats to summarize
    :param digest_stats: stats to digest
    :return: summary with digest
    """
    if digest_stats is None and isinstance(stats, UnitTestRunDeltaResults):
        raise ValueError('stats must be UnitTestRunResults when no digest_stats is given')
    summary = get_long_summary_md(stats)
    digest = get_digest_from_stats(stats if digest_stats is None else digest_stats)
    return f'{summary}\n{digest_header}{digest}'


def get_case_messages(case_results: UnitTestCaseResults) -> CaseMessages:
    messages = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for key in case_results:
        for state in case_results[key]:
            for case in case_results[key][state]:
                message = case.message if case.result in ['skipped', 'disabled'] else case.content
                messages[key][state][message].append(case)
    return CaseMessages(messages)


@dataclass(frozen=True)
class Annotation:
    path: str
    start_line: int
    end_line: int
    start_column: Optional[int]
    end_column: Optional[int]
    annotation_level: str
    message: str
    title: Optional[str]
    raw_details: Optional[str]

    def to_dict(self) -> Mapping[str, Any]:
        dictionary = self.__dict__.copy()
        dictionary['message'] = abbreviate_bytes(dictionary['message'], 64000)
        dictionary['title'] = abbreviate(dictionary['title'], 255)
        dictionary['raw_details'] = abbreviate(dictionary['raw_details'], 64000)
        if not dictionary.get('start_column'):
            del dictionary['start_column']
        if not dictionary.get('end_column'):
            del dictionary['end_column']
        if not dictionary.get('title'):
            del dictionary['title']
        if not dictionary.get('raw_details'):
            del dictionary['raw_details']
        return dictionary


def get_case_annotation(messages: CaseMessages,
                        key: Tuple[Optional[str], Optional[str], Optional[str]],
                        state: str,
                        message: Optional[str],
                        report_individual_runs: bool) -> Annotation:
    case = messages[key][state][message][0]
    same_cases = len(messages[key][state][message] if report_individual_runs else
                     [case
                      for m in messages[key][state]
                      for case in messages[key][state][m]])
    all_cases = len([case
                     for s in messages[key]
                     for m in messages[key][s]
                     for case in messages[key][s][m]])
    same_result_files = [case.result_file
                         for case in (messages[key][state][message] if report_individual_runs else
                                      [c
                                       for m in messages[key][state]
                                       for c in messages[key][state][m]])
                         if case.result_file]
    test_file = case.test_file
    line = case.line or 0
    test_name = case.test_name if case.test_name else 'Unknown test'
    class_name = case.class_name
    title = test_name if not class_name else f'{test_name} ({class_name})'
    title_state = \
        'pass' if state == 'success' else \
        'failed' if state == 'failure' else \
        'with error' if state == 'error' else \
        'skipped'
    if all_cases > 1:
        if same_cases == all_cases:
            title = f'All {all_cases} runs {title_state}: {title}'
        else:
            title = f'{same_cases} out of {all_cases} runs {title_state}: {title}'
    else:
        title = f'{title} {title_state}'

    level = (
        'warning' if case.result == 'failure' else
        'failure' if case.result == 'error' else  # failure is used for test errors
        'notice'
    )

    return Annotation(
        path=test_file or class_name or '/',
        start_line=line,
        end_line=line,
        start_column=None,
        end_column=None,
        annotation_level=level,
        message='\n'.join(sorted(same_result_files)),
        title=title,
        raw_details=message
    )


def get_case_annotations(case_results: UnitTestCaseResults,
                         report_individual_runs: bool) -> List[Annotation]:
    messages = get_case_messages(case_results)
    return [
        get_case_annotation(messages, key, state, message, report_individual_runs)
        for key in messages
        for state in messages[key] if state not in ['success', 'skipped']
        for message in (messages[key][state] if report_individual_runs else
                        [list(messages[key][state].keys())[0]])
    ]


def get_error_annotation(error: ParseError) -> Annotation:
    return Annotation(
        path=error.file,
        start_line=error.line or 0,
        end_line=error.line or 0,
        start_column=error.column,
        end_column=error.column,
        annotation_level='failure',
        message=error.message,
        title=f'Error processing result file',
        raw_details=error.file
    )


def get_error_annotations(parse_errors: List[ParseError]) -> List[Annotation]:
    return [get_error_annotation(error) for error in parse_errors]


def get_test_name(file_name: Optional[str],
                  class_name: Optional[str],
                  test_name: Optional[str]) -> str:
    if not test_name:
        test_name = 'Unknown test'

    name = []
    token = ' ‑ '  # U+2011 non-breaking hyphen
    for part in [file_name, class_name, test_name]:
        if part:
            name.append(part.replace(token, ' ‐ '))  # U+2010 breaking hyphen

    return token.join(name)


def get_all_tests_list(cases: UnitTestCaseResults) -> List[str]:
    if not cases:
        return []
    return [get_test_name(file_name, class_name, test_name)
            for (file_name, class_name, test_name) in cases.keys()]


def get_skipped_tests_list(cases: UnitTestCaseResults) -> List[str]:
    if not cases:
        return []
    return [get_test_name(file_name, class_name, test_name)
            for (file_name, class_name, test_name), result in cases.items()
            if 'skipped' in result and len(result) == 1]


def get_all_tests_list_annotation(cases: UnitTestCaseResults, max_chunk_size: int = 64000) -> List[Annotation]:
    return get_test_list_annotation(get_all_tests_list(cases), 'test', max_chunk_size)


def get_skipped_tests_list_annotation(cases: UnitTestCaseResults, max_chunk_size: int = 64000) -> List[Annotation]:
    return get_test_list_annotation(get_skipped_tests_list(cases), 'skipped test', max_chunk_size)


def get_test_list_annotation(tests: List[str], label: str, max_chunk_size: int = 64000) -> List[Annotation]:
    if len(tests) == 0:
        return []

    # the max_chunk_size must not be larger than the abbreviate_bytes limit in Annotation.to_dict
    test_chunks = chunk_test_list(sorted(tests), '\n', max_chunk_size)

    if len(test_chunks) == 1:
        if len(tests) == 1:
            title = f'{len(tests)} {label} found'
            message = f'There is 1 {label}, see "Raw output" for the name of the {label}.'
        else:
            title = f'{len(tests)} {label}s found'
            message = f'There are {len(tests)} {label}s, see "Raw output" for the full list of {label}s.'

        return [create_tests_list_annotation(title=title, message=message, raw_details='\n'.join(test_chunks[0]))]

    first = 1
    annotations = []
    for chunk in test_chunks:
        last = first + len(chunk) - 1
        title = f'{len(tests)} {label}s found (test {first} to {last})'
        message = f'There are {len(tests)} {label}s, see "Raw output" for the list of {label}s {first} to {last}.'
        annotation = create_tests_list_annotation(title=title, message=message, raw_details='\n'.join(chunk))
        annotations.append(annotation)
        first = last + 1

    return annotations


def chunk_test_list(tests: List[str], delimiter: str, max_chunk_size: int) -> List[List[str]]:
    if not tests:
        return []

    sizes = [len(f'{test}{delimiter}'.encode('utf8')) for test in tests]
    if sum(sizes) <= max_chunk_size:
        return [tests]

    chunks = []
    while tests:
        size = 0
        length = 0
        while length < len(tests) and size + sizes[length] < max_chunk_size:
            size = size + sizes[length]
            length = length + 1

        chunks.append(tests[:length])
        tests = tests[length:]
        sizes = sizes[length:]

    return chunks


def create_tests_list_annotation(title: str, message: str, raw_details: Optional[str]) -> Annotation:
    return Annotation(
        path='.github',
        start_line=0,
        end_line=0,
        start_column=None,
        end_column=None,
        annotation_level='notice',
        message=message,
        title=title,
        raw_details=raw_details
    )
