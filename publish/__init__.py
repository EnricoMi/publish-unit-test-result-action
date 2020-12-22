import base64
import gzip
import json
import logging
import re
from collections import defaultdict
from typing import List, Any, Union, Optional, Tuple, Mapping

from dataclasses import dataclass

from unittestresults import Numeric, UnitTestCaseResults, UnitTestRunResults, \
    UnitTestRunDeltaResults, UnitTestRunResultsOrDeltaResults, ParseError


class CaseMessages(defaultdict):
    def __init__(self, items=None):
        if items is None:
            items = []
        super(CaseMessages, self).__init__(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))),
            items
        )


logger = logging.getLogger('publish')
digest_prefix = '[test-results]:data:application/gzip;base64,'
digit_space = '  '
punctuation_space = ' '

hide_comments_mode_off = "off"
hide_comments_mode_all_but_latest = "all but latest"
hide_comments_mode_orphaned = "orphaned commits"
hide_comments_modes = [
    hide_comments_mode_off,
    hide_comments_mode_all_but_latest,
    hide_comments_mode_orphaned
]


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
    return '{}{}'.format(sign, string)


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
            ' {} '.format(extra) if extra != '' else ''
        ])
    else:
        logger.warning('unsupported stats number type {}: {}'.format(type(number), number))
        return 'N/A'


def as_stat_duration(duration: Optional[Union[int, Numeric]], label=None) -> str:
    if duration is None:
        if label:
            return 'N/A {}'.format(label)
        return 'N/A'
    if isinstance(duration, float):
        duration = int(duration)
    if isinstance(duration, int):
        duration = abs(duration)
        strings = []
        for unit in ['s', 'm', 'h']:
            if unit == 's' or duration:
                strings.insert(0, '{}{}'.format(duration % 60, unit))
                duration //= 60
        string = ' '.join(strings)
        if label:
            return '{} {}'.format(string, label)
        return string
    elif isinstance(duration, dict):
        delta = duration.get('delta')
        duration = duration.get('duration')
        sign = '' if delta is None else '±' if delta == 0 else '+' if delta > 1 else '-'
        if delta and abs(delta) >= 60:
            sign += ' '
        return as_stat_duration(duration, label) + (' {}{}'.format(
            sign,
            as_stat_duration(delta)
        ) if delta is not None else '')
    else:
        logger.warning('unsupported stats duration type {}: {}'.format(type(duration), duration))
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
                return '{} parse errors'.format(perrors)
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

            summary = ['{}'.format(as_stat_number(number, 0, 0, label))
                       for number, label in [(perrors, 'parse errors'),
                                             (error, 'errors'), (failure, 'fail'),
                                             (skipped, 'skipped'), (success, 'pass')]
                       if number > 0]
            summary = ', '.join(summary)

            # when all except tests are None or 0
            if len(summary) == 0:
                return '{} found'.format(as_stat_number(tests, 0, 0, 'tests'))
            return summary

    if tests is None or tests == 0 or duration is None:
        return get_test_summary()

    return '{} in {}'.format(get_test_summary(), as_stat_duration(duration))


def get_short_summary_md(stats: UnitTestRunResultsOrDeltaResults) -> str:
    """Provides a single-line summary with markdown for the given stats."""
    md = ('{tests} {tests_succ} {tests_skip} {tests_fail} {tests_error}'.format(
        tests=as_stat_number(stats.tests, 0, 0, 'tests'),
        tests_succ=as_stat_number(stats.tests_succ, 0, 0, ':heavy_check_mark:'),
        tests_skip=as_stat_number(stats.tests_skip, 0, 0, ':zzz:'),
        tests_fail=as_stat_number(stats.tests_fail, 0, 0, ':x:'),
        tests_error=as_stat_number(stats.tests_error, 0, 0, ':fire:'),
    ))
    return md


def get_long_summary_md(stats: UnitTestRunResultsOrDeltaResults,
                        details_url: Optional[str] = None) -> str:
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
        duration=as_stat_duration(stats.duration, ':stopwatch:')
    )

    tests_error_part = ' {tests_error}'.format(
        tests_error=as_stat_number(stats.tests_error, error_digits, error_delta_digits, ':fire:')
    ) if get_magnitude(stats.tests_error) else ''
    tests_line = '{tests} {tests_succ} {tests_skip} {tests_fail}{tests_error_part}\n'.format(
        tests=as_stat_number(stats.tests, files_digits, files_delta_digits, 'tests'),
        tests_succ=as_stat_number(stats.tests_succ, success_digits, success_delta_digits, ':heavy_check_mark:'),
        tests_skip=as_stat_number(stats.tests_skip, skip_digits, skip_delta_digits, ':zzz:'),
        tests_fail=as_stat_number(stats.tests_fail, fail_digits, fail_delta_digits, ':x:'),
        tests_error_part=tests_error_part
    )

    runs_error_part = ' {runs_error}'.format(
        runs_error=as_stat_number(stats.runs_error, error_digits, error_delta_digits, ':fire:')
    ) if get_magnitude(stats.runs_error) else ''
    runs_line = '{runs} {runs_succ} {runs_skip} {runs_fail}{runs_error_part}\n'.format(
        runs=as_stat_number(stats.runs, files_digits, files_delta_digits, 'runs '),
        runs_succ=as_stat_number(stats.runs_succ, success_digits, success_delta_digits, ':heavy_check_mark:'),
        runs_skip=as_stat_number(stats.runs_skip, skip_digits, skip_delta_digits, ':zzz:'),
        runs_fail=as_stat_number(stats.runs_fail, fail_digits, fail_delta_digits, ':x:'),
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

    commit_line = '\nResults for commit {commit}.{compare}\n'.format(
        commit=as_short_commit(commit),
        compare=' ± Comparison against {reference_type} commit {reference_commit}.'.format(
            reference_type=reference_type,
            reference_commit=as_short_commit(reference_commit)
        ) if reference_type and reference_commit else ''
    )

    md = ('{misc}{tests}{runs}{details}{commit}'.format(
        misc=misc_line,
        tests=tests_line,
        runs=runs_line if not hide_runs else '',
        details=details_line if details_url and details_on else '',
        commit=commit_line
    ))
    return md


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
    return '{}\n{}{}'.format(summary, digest_prefix, digest)


def get_case_messages(case_results: UnitTestCaseResults) -> CaseMessages:
    messages = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for key in case_results:
        for state in case_results[key]:
            for case in case_results[key][state]:
                message = case.message if case.result == 'skipped' else case.content
                messages[key][state][message].append(case)
    return messages


@dataclass(frozen=True)
class Annotation:
    path: str
    start_line: int
    end_line: int
    start_column: Optional[int]
    end_column: Optional[int]
    annotation_level: str
    message: str
    title: str
    raw_details: Optional[str]

    def to_dict(self) -> Mapping[str, Any]:
        dictionary = self.__dict__.copy()
        if not dictionary.get('start_column'):
            del dictionary['start_column']
        if not dictionary.get('end_column'):
            del dictionary['end_column']
        if not dictionary.get('raw_details'):
            del dictionary['raw_details']
        return dictionary


def get_case_annotation(messages: CaseMessages,
                        key: str, state: str, message: Optional[str],
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
    title = test_name if not class_name else '{} ({})'.format(test_name, class_name)
    title_state = \
        'pass' if state == 'success' else \
        'failed' if state == 'failure' else \
        'with error' if state == 'error' else \
        'skipped'
    if all_cases > 1:
        if same_cases == all_cases:
            title = 'All {} runs {}: {}'.format(all_cases, title_state, title)
        else:
            title = '{} out of {} runs {}: {}'.format(same_cases, all_cases, title_state, title)
    else:
        title = '{} {}'.format(title, title_state)

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
        message='\n'.join(same_result_files),
        title=title,
        raw_details=message
    )


def get_error_annotation(error: ParseError) -> Annotation:
    return Annotation(
        path=error.file,
        start_line=error.line or 0,
        end_line=error.line or 0,
        start_column=error.column,
        end_column=error.column,
        annotation_level='failure',
        message=error.file,
        title=f'Error processing result file',
        raw_details=error.message
    )


def get_annotations(case_results: UnitTestCaseResults,
                    parse_errors: List[ParseError],
                    report_individual_runs: bool) -> List[Annotation]:
    messages = get_case_messages(case_results)
    case_annotations = [
        get_case_annotation(messages, key, state, message, report_individual_runs)
        for key in messages
        for state in messages[key] if state not in ['success', 'skipped']
        for message in (messages[key][state] if report_individual_runs else
                        [list(messages[key][state].keys())[0]])
    ]

    error_annotations = [get_error_annotation(error) for error in parse_errors]

    return error_annotations + case_annotations
