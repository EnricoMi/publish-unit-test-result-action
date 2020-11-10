import mock
import contextlib
import locale
import unittest

from publish import *
from unittestresults import get_test_results
from junit import parse_junit_xml_files
from test import d, n
from unittestresults import get_stats, UnitTestCase


@contextlib.contextmanager
def temp_locale(encoding) -> Any:
    old_locale = locale.getlocale()
    locale.setlocale(locale.LC_ALL, encoding)
    try:
        res = yield
    finally:
        locale.setlocale(locale.LC_ALL, old_locale)
    return res


class PublishTest(unittest.TestCase):
    old_locale = None

    def test_get_formatted_digits(self):
        self.assertEqual(get_formatted_digits(None), (3, 0))
        self.assertEqual(get_formatted_digits(None, 1), (3, 0))
        self.assertEqual(get_formatted_digits(None, 123), (3, 0))
        self.assertEqual(get_formatted_digits(None, 1234), (5, 0))
        self.assertEqual(get_formatted_digits(0), (1, 0))
        self.assertEqual(get_formatted_digits(1, 2, 3), (1, 0))
        self.assertEqual(get_formatted_digits(10), (2, 0))
        self.assertEqual(get_formatted_digits(100), (3, 0))
        self.assertEqual(get_formatted_digits(1234, 123, 0), (5, 0))
        with temp_locale('en_US.utf8'):
            self.assertEqual(get_formatted_digits(1234, 123, 0), (5, 0))
        with temp_locale('de_DE.utf8'):
            self.assertEqual(get_formatted_digits(1234, 123, 0), (5, 0))

        self.assertEqual(get_formatted_digits(dict()), (3, 3))
        self.assertEqual(get_formatted_digits(dict(number=1)), (1, 3))
        self.assertEqual(get_formatted_digits(dict(number=12)), (2, 3))
        self.assertEqual(get_formatted_digits(dict(number=123)), (3, 3))
        self.assertEqual(get_formatted_digits(dict(number=1234)), (5, 3))
        with temp_locale('en_US.utf8'):
            self.assertEqual(get_formatted_digits(dict(number=1234)), (5, 3))
        with temp_locale('de_DE.utf8'):
            self.assertEqual(get_formatted_digits(dict(number=1234)), (5, 3))

        self.assertEqual(get_formatted_digits(dict(delta=1)), (3, 1))
        self.assertEqual(get_formatted_digits(dict(number=1, delta=1)), (1, 1))
        self.assertEqual(get_formatted_digits(dict(number=1, delta=12)), (1, 2))
        self.assertEqual(get_formatted_digits(dict(number=1, delta=123)), (1, 3))
        self.assertEqual(get_formatted_digits(dict(number=1, delta=1234)), (1, 5))
        with temp_locale('en_US.utf8'):
            self.assertEqual(get_formatted_digits(dict(number=1, delta=1234)), (1, 5))
        with temp_locale('de_DE.utf8'):
            self.assertEqual(get_formatted_digits(dict(number=1, delta=1234)), (1, 5))

    def test_get_magnitude(self):
        self.assertEqual(None, get_magnitude(None))
        self.assertEqual(+0, get_magnitude(+0))
        self.assertEqual(-1, get_magnitude(-1))
        self.assertEqual(+2, get_magnitude(+2))
        self.assertEqual(None, get_magnitude(dict()))
        self.assertEqual(+0, get_magnitude(dict(number=+0)))
        self.assertEqual(+1, get_magnitude(dict(number=+1)))
        self.assertEqual(-2, get_magnitude(dict(number=-2)))
        self.assertEqual(3, get_magnitude(dict(number=3, delta=5)))
        self.assertEqual(3, get_magnitude(dict(duration=3)))
        self.assertEqual(3, get_magnitude(dict(duration=3, delta=5)))
        self.assertEqual(None, get_magnitude(dict(delta=5)))

    def test_get_delta(self):
        self.assertEqual(None, get_delta(None))
        self.assertEqual(None, get_delta(+0))
        self.assertEqual(None, get_delta(-1))
        self.assertEqual(None, get_delta(+2))
        self.assertEqual(None, get_delta(dict()))
        self.assertEqual(None, get_delta(dict(number=+0)))
        self.assertEqual(None, get_delta(dict(number=+1)))
        self.assertEqual(None, get_delta(dict(number=-2)))
        self.assertEqual(5, get_delta(dict(number=3, delta=5)))
        self.assertEqual(None, get_delta(dict(duration=3)))
        self.assertEqual(5, get_delta(dict(duration=3, delta=5)))
        self.assertEqual(5, get_delta(dict(delta=5)))

    def test_as_short_commit(self):
        self.assertEqual(as_short_commit(None), None)
        self.assertEqual(as_short_commit(''), None)
        self.assertEqual(as_short_commit('commit'), 'commit')
        self.assertEqual(as_short_commit('0123456789abcdef'), '01234567')
        self.assertEqual(as_short_commit('b469da3d223225fa3f014a3c9e9466b42a1471c5'), 'b469da3d')

    def test_as_delta(self):
        self.assertEqual(as_delta(0, 1), '±0')
        self.assertEqual(as_delta(+1, 1), '+1')
        self.assertEqual(as_delta(-2, 1), ' - 2')

        self.assertEqual(as_delta(0, 2), '±  0')
        self.assertEqual(as_delta(+1, 2), '+  1')
        self.assertEqual(as_delta(-2, 2), ' -   2')

        self.assertEqual(as_delta(1, 5), '+       1')
        self.assertEqual(as_delta(12, 5), '+     12')
        self.assertEqual(as_delta(123, 5), '+   123')
        self.assertEqual(as_delta(1234, 5), '+1 234')
        self.assertEqual(as_delta(1234, 6), '+  1 234')
        self.assertEqual(as_delta(123, 6), '+     123')

        with temp_locale('en_US.utf8'):
            self.assertEqual(as_delta(1234, 5), '+1 234')
            self.assertEqual(as_delta(1234, 6), '+  1 234')
            self.assertEqual(as_delta(123, 6), '+     123')
        with temp_locale('de_DE.utf8'):
            self.assertEqual(as_delta(1234, 5), '+1 234')
            self.assertEqual(as_delta(1234, 6), '+  1 234')
            self.assertEqual(as_delta(123, 6), '+     123')

    def test_as_stat_number(self):
        label = 'unit'
        self.assertEqual(as_stat_number(None, 1, 0, label), 'N/A unit')

        self.assertEqual(as_stat_number(1, 1, 0, label), '1 unit')
        self.assertEqual(as_stat_number(123, 6, 0, label), '     123 unit')
        self.assertEqual(as_stat_number(1234, 6, 0, label), '  1 234 unit')
        self.assertEqual(as_stat_number(12345, 6, 0, label), '12 345 unit')

        with temp_locale('en_US.utf8'):
            self.assertEqual(as_stat_number(123, 6, 0, label), '     123 unit')
            self.assertEqual(as_stat_number(1234, 6, 0, label), '  1 234 unit')
            self.assertEqual(as_stat_number(12345, 6, 0, label), '12 345 unit')
        with temp_locale('de_DE.utf8'):
            self.assertEqual(as_stat_number(123, 6, 0, label), '     123 unit')
            self.assertEqual(as_stat_number(1234, 6, 0, label), '  1 234 unit')
            self.assertEqual(as_stat_number(12345, 6, 0, label), '12 345 unit')

        self.assertEqual(as_stat_number(dict(number=1), 1, 0, label), '1 unit')

        self.assertEqual(as_stat_number(dict(number=1, delta=-1), 1, 1, label), '1 unit  - 1 ')
        self.assertEqual(as_stat_number(dict(number=2, delta=+0), 1, 1, label), '2 unit ±0 ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+1), 1, 1, label), '3 unit +1 ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+1), 1, 2, label), '3 unit +  1 ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+1), 2, 2, label), '  3 unit +  1 ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+1234), 1, 6, label), '3 unit +  1 234 ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+12345), 1, 6, label), '3 unit +12 345 ')
        with temp_locale('en_US.utf8'):
            self.assertEqual(as_stat_number(dict(number=3, delta=+1234), 1, 6, label), '3 unit +  1 234 ')
            self.assertEqual(as_stat_number(dict(number=3, delta=+12345), 1, 6, label), '3 unit +12 345 ')
        with temp_locale('de_DE.utf8'):
            self.assertEqual(as_stat_number(dict(number=3, delta=+1234), 1, 6, label), '3 unit +  1 234 ')
            self.assertEqual(as_stat_number(dict(number=3, delta=+12345), 1, 6, label), '3 unit +12 345 ')

        self.assertEqual(as_stat_number(dict(delta=-1), 3, 1, label), 'N/A unit  - 1 ')

        self.assertEqual(as_stat_number(dict(number=1, delta=-2, new=3), 1, 1, label), '1 unit  - 2, 3 new ')
        self.assertEqual(as_stat_number(dict(number=2, delta=+0, new=3, gone=4), 1, 1, label), '2 unit ±0, 3 new, 4 gone ')
        self.assertEqual(as_stat_number(dict(number=3, delta=+1, gone=4), 1, 1, label), '3 unit +1, 4 gone ')

    def test_as_stat_duration(self):
        label = 'time'
        self.assertEqual(as_stat_duration(None, label), 'N/A time')
        self.assertEqual(as_stat_duration(0, None), '0s')
        self.assertEqual(as_stat_duration(0, label), '0s time')
        self.assertEqual(as_stat_duration(12, label), '12s time')
        self.assertEqual(as_stat_duration(72, label), '1m 12s time')
        self.assertEqual(as_stat_duration(3754, label), '1h 2m 34s time')
        self.assertEqual(as_stat_duration(-3754, label), '1h 2m 34s time')

        self.assertEqual(as_stat_duration(d(3754), label), '1h 2m 34s time')
        self.assertEqual(as_stat_duration(d(3754, 0), label), '1h 2m 34s time ±0s')
        self.assertEqual(as_stat_duration(d(3754, 1234), label), '1h 2m 34s time + 20m 34s')
        self.assertEqual(as_stat_duration(d(3754, -123), label), '1h 2m 34s time - 2m 3s')
        self.assertEqual(as_stat_duration(dict(delta=123), label), 'N/A time + 2m 3s')

    def test_get_stats_digest_undigest(self):
        digest = get_digest_from_stats(UnitTestRunResults(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        ))
        self.assertTrue(isinstance(digest, str))
        self.assertTrue(len(digest) > 100)
        stats = get_stats_from_digest(digest)
        self.assertEqual(stats, UnitTestRunResults(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        ))

    def test_digest_ungest_string(self):
        digest = digest_string('abc')
        self.assertTrue(isinstance(digest, str))
        self.assertTrue(len(digest) > 10)
        string = ungest_string(digest)
        self.assertEqual(string, 'abc')

    def test_get_stats_from_digest(self):
        self.assertEqual(
            get_stats_from_digest('H4sIALSWTl8C/03OzQ6DIBAE4FcxnD10tf8v0xDEZFOVZoGT6b'
                                  't3qC7tbebbMGE1I08+mntDbWNi5vQtHcqQxSYOC2qPikMqp6Pm'
                                  'R8zO+Vjs9LMnvwDnCqPlCXCp4EWCQK4QyUt5ftvj3yIdqm2LRA'
                                  'r7InUKukjlmy7MMyc0Te8PumEONuMAAAA='),
            UnitTestRunResults(
                files=1, suites=2, duration=3,
                tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
                runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
                commit='commit'
            )
        )

    def test_get_short_summary(self):
        self.assertEqual('No tests found', get_short_summary(UnitTestRunResults(files=0, suites=0, duration=123, tests=0, tests_succ=0, tests_skip=0, tests_fail=0, tests_error=0, runs=0, runs_succ=0, runs_skip=0, runs_fail=0, runs_error=0, commit='commit')))
        self.assertEqual('10 tests found in 2m 3s', get_short_summary(UnitTestRunResults(files=1, suites=2, duration=123, tests=10, tests_succ=0, tests_skip=0, tests_fail=0, tests_error=0, runs=0, runs_succ=0, runs_skip=0, runs_fail=0, runs_error=0, commit='commit')))
        self.assertEqual('All 10 tests pass in 2m 3s', get_short_summary(UnitTestRunResults(files=1, suites=2, duration=123, tests=10, tests_succ=10, tests_skip=0, tests_fail=0, tests_error=0, runs=0, runs_succ=0, runs_skip=0, runs_fail=0, runs_error=0, commit='commit')))
        self.assertEqual('All 9 tests pass, 1 skipped in 2m 3s', get_short_summary(UnitTestRunResults(files=1, suites=2, duration=123, tests=10, tests_succ=9, tests_skip=1, tests_fail=0, tests_error=0, runs=0, runs_succ=0, runs_skip=0, runs_fail=0, runs_error=0, commit='commit')))
        self.assertEqual('2 fail, 1 skipped, 7 pass in 2m 3s', get_short_summary(UnitTestRunResults(files=1, suites=2, duration=123, tests=10, tests_succ=7, tests_skip=1, tests_fail=2, tests_error=0, runs=0, runs_succ=0, runs_skip=0, runs_fail=0, runs_error=0, commit='commit')))
        self.assertEqual('3 errors, 2 fail, 1 skipped, 4 pass in 2m 3s', get_short_summary(UnitTestRunResults(files=1, suites=2, duration=123, tests=10, tests_succ=4, tests_skip=1, tests_fail=2, tests_error=3, runs=0, runs_succ=0, runs_skip=0, runs_fail=0, runs_error=0, commit='commit')))
        self.assertEqual('2 fail, 8 pass in 2m 3s', get_short_summary(UnitTestRunResults(files=1, suites=2, duration=123, tests=10, tests_succ=8, tests_skip=0, tests_fail=2, tests_error=0, runs=0, runs_succ=0, runs_skip=0, runs_fail=0, runs_error=0, commit='commit')))
        self.assertEqual('3 errors, 7 pass in 2m 3s', get_short_summary(UnitTestRunResults(files=1, suites=2, duration=123, tests=10, tests_succ=7, tests_skip=0, tests_fail=0, tests_error=3, runs=0, runs_succ=0, runs_skip=0, runs_fail=0, runs_error=0, commit='commit')))

    def test_get_short_summary_md(self):
        self.assertEqual(get_short_summary_md(UnitTestRunResults(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        )), ('4 tests 5 :heavy_check_mark: 6 :zzz: 7 :x: 8 :fire:'))

    def test_get_short_summary_md_with_delta(self):
        self.assertEqual(get_short_summary_md(UnitTestRunDeltaResults(
            files=n(1, 2), suites=n(2, -3), duration=d(3, 4),
            tests=n(4, -5), tests_succ=n(5, 6), tests_skip=n(6, -7), tests_fail=n(7, 8), tests_error=n(8, -9),
            runs=n(9, 10), runs_succ=n(10, -11), runs_skip=n(11, 12), runs_fail=n(12, -13), runs_error=n(13, 14),
            commit='commit',
            reference_type='type', reference_commit='0123456789abcdef'
        )), ('4 tests  - 5  5 :heavy_check_mark: +6  6 :zzz:  - 7  7 :x: +8  8 :fire:  - 9 '))

    def test_get_long_summary_md_with_single_runs(self):
        self.assertEqual(get_long_summary_md(UnitTestRunResults(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=4, runs_succ=5, runs_skip=6, runs_fail=7, runs_error=8,
            commit='commit'
        )), ('1 files  2 suites   3s :stopwatch:\n'
            '4 tests 5 :heavy_check_mark: 6 :zzz: 7 :x: 8 :fire:\n'
            '\n'
            'results for commit commit\n'))

    def test_get_long_summary_md_with_multiple_runs(self):
        self.assertEqual(get_long_summary_md(UnitTestRunResults(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=0,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=0,
            commit='commit'
        )), ('1 files    2 suites   3s :stopwatch:\n'
            '4 tests   5 :heavy_check_mark:   6 :zzz:   7 :x:\n'
            '9 runs  10 :heavy_check_mark: 11 :zzz: 12 :x:\n'
            '\n'
            'results for commit commit\n'))

    def test_get_long_summary_md_with_errors(self):
        self.assertEqual(get_long_summary_md(UnitTestRunResults(
            files=1, suites=2, duration=3,
            tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
            runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
            commit='commit'
        )), ('1 files    2 suites   3s :stopwatch:\n'
            '4 tests   5 :heavy_check_mark:   6 :zzz:   7 :x:   8 :fire:\n'
            '9 runs  10 :heavy_check_mark: 11 :zzz: 12 :x: 13 :fire:\n'
            '\n'
            'results for commit commit\n'))

    def test_get_long_summary_md_with_deltas(self):
        self.assertEqual(get_long_summary_md(UnitTestRunDeltaResults(
            files=n(1, 2), suites=n(2, -3), duration=d(3, 4),
            tests=n(4, -5), tests_succ=n(5, 6), tests_skip=n(6, -7), tests_fail=n(7, 8), tests_error=n(8, -9),
            runs=n(9, 10), runs_succ=n(10, -11), runs_skip=n(11, 12), runs_fail=n(12, -13), runs_error=n(13, 14),
            commit='123456789abcdef0', reference_type='type', reference_commit='0123456789abcdef'
        )), ('1 files  +  2    2 suites   - 3   3s :stopwatch: +4s\n'
            '4 tests  -   5    5 :heavy_check_mark: +  6    6 :zzz:  -   7    7 :x: +  8    8 :fire:  -   9 \n'
            '9 runs  +10  10 :heavy_check_mark:  - 11  11 :zzz: +12  12 :x:  - 13  13 :fire: +14 \n'
            '\n'
            'results for commit 12345678 ± comparison against type commit 01234567\n'))

    def test_get_long_summary_with_digest_md_with_single_run(self):
        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            actual = get_long_summary_with_digest_md(
                UnitTestRunResults(
                    files=1, suites=2, duration=3,
                    tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
                    runs=4, runs_succ=5, runs_skip=6, runs_fail=7, runs_error=8,
                    commit='commit'
                )
            )

        self.assertEqual(actual, '1 files  2 suites   3s :stopwatch:\n'
                                 '4 tests 5 :heavy_check_mark: 6 :zzz: 7 :x: 8 :fire:\n'
                                 '\n'
                                 'results for commit commit\n'
                                 '\n'
                                 '[test-results]:data:application/gzip;base64,H4sIAAAAAAAC/12MSQqAMBAEvyI5e3EXPyMSIwwukUlyEv9uJxIVb13VUIeYaFFGdEmWJsI4sgFywOh4sKQ3YAHEYf1Vxt0bJ6Uy3lWvm2mHqB8xDbRANI9QzJphWhh2W0z6+Sve6g0G/vQCf3NSrytZQFznBZMgccHfAAAA')

    def test_get_long_summary_with_digest_md_with_multiple_runs(self):
        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            actual = get_long_summary_with_digest_md(
                UnitTestRunResults(
                    files=1, suites=2, duration=3,
                    tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=0,
                    runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=0,
                    commit='commit'
                )
            )

        self.assertEqual(actual, '1 files    2 suites   3s :stopwatch:\n'
                                 '4 tests   5 :heavy_check_mark:   6 :zzz:   7 :x:\n'
                                 '9 runs  10 :heavy_check_mark: 11 :zzz: 12 :x:\n'
                                 '\n'
                                 'results for commit commit\n'
                                 '\n'
                                 '[test-results]:data:application/gzip;base64,H4sIAAAAAAAC/03MSw6DMAwE0KugrFlgaEH0MhVKg2TxSeUkq4q7MwGSspt5luenRp6NU6+CykK5wP4oNconyODZrqgNKg4+nh4pv13Q2rhoz79N/AW0GcaBZ0CXwYhYgVQQCWt87694W6Qq27lIlOBapDrBfVHbZWGPktK2A4fA80fiAAAA')

    def test_get_long_summary_with_digest_md_with_errors(self):
        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            actual = get_long_summary_with_digest_md(
                UnitTestRunResults(
                    files=1, suites=2, duration=3,
                    tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
                    runs=9, runs_succ=10, runs_skip=11, runs_fail=12, runs_error=13,
                    commit='commit'
                )
            )

        self.assertEqual(actual, '1 files    2 suites   3s :stopwatch:\n'
                                 '4 tests   5 :heavy_check_mark:   6 :zzz:   7 :x:   8 :fire:\n'
                                 '9 runs  10 :heavy_check_mark: 11 :zzz: 12 :x: 13 :fire:\n'
                                 '\n'
                                 'results for commit commit\n'
                                 '\n'
                                 '[test-results]:data:application/gzip;base64,H4sIAAAAAAAC/03OzQ6DIBAE4FcxnD10tf8v0xDEZFOVZoGT6bt3qC7tbebbMGE1I08+mntDbWNi5vQtHcqQxSYOC2qPikMqp6PmR8zO+Vjs9LMnvwDnCqPlCXCp4EWCQK4QyUt5ftvj3yIdqm2LRAr7InUKukjlmy7MMyc0Te8PumEONuMAAAA=')

    def test_get_long_summary_with_digest_md_with_delta(self):
        # makes gzipped digest deterministic
        with mock.patch('gzip.time.time', return_value=0):
            actual = get_long_summary_with_digest_md(
                UnitTestRunDeltaResults(
                    files=n(1, 2), suites=n(2, -3), duration=d(3, 4),
                    tests=n(4, -5), tests_succ=n(5, 6), tests_skip=n(6, -7), tests_fail=n(7, 8), tests_error=n(8, -9),
                    runs=n(9, 10), runs_succ=n(10, -11), runs_skip=n(11, 12), runs_fail=n(12, -13), runs_error=n(13, 14),
                    commit='123456789abcdef0', reference_type='type', reference_commit='0123456789abcdef'
                ), UnitTestRunResults(
                    files=1, suites=2, duration=3,
                    tests=4, tests_succ=5, tests_skip=6, tests_fail=7, tests_error=8,
                    runs=4, runs_succ=5, runs_skip=6, runs_fail=7, runs_error=8,
                    commit='commit'
                )
            )

        self.assertEqual(actual, '1 files  +  2    2 suites   - 3   3s :stopwatch: +4s\n'
                                 '4 tests  -   5    5 :heavy_check_mark: +  6    6 :zzz:  -   7    7 :x: +  8    8 :fire:  -   9 \n'
                                 '9 runs  +10  10 :heavy_check_mark:  - 11  11 :zzz: +12  12 :x:  - 13  13 :fire: +14 \n'
                                 '\n'
                                 'results for commit 12345678 ± comparison against type commit 01234567\n'
                                 '\n'
                                 '[test-results]:data:application/gzip;base64,H4sIAAAAAAAC/12MSQqAMBAEvyI5e3EXPyMSIwwukUlyEv9uJxIVb13VUIeYaFFGdEmWJsI4sgFywOh4sKQ3YAHEYf1Vxt0bJ6Uy3lWvm2mHqB8xDbRANI9QzJphWhh2W0z6+Sve6g0G/vQCf3NSrytZQFznBZMgccHfAAAA')

    def test_get_long_summary_with_digest_md_with_delta_results_only(self):
        with self.assertRaises(ValueError) as context:
            get_long_summary_with_digest_md(UnitTestRunDeltaResults(
                files=n(1, 2), suites=n(2, -3), duration=d(3, 4),
                tests=n(4, -5), tests_succ=n(5, 6), tests_skip=n(6, -7), tests_fail=n(7, 8), tests_error=n(8, -9),
                runs=n(9, 10), runs_succ=n(10, -11), runs_skip=n(11, 12), runs_fail=n(12, -13), runs_error=n(13, 14),
                commit='123456789abcdef0', reference_type='type', reference_commit='0123456789abcdef'
            ))
        self.assertIn('stats must be UnitTestRunResults when no digest_stats is given', context.exception.args)

    def test_get_case_messages(self):
        results = UnitTestCaseResults([
            ('class1::test1', dict([
                ('success', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1.0),
                    UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1.1),
                    UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='success', message='message2', content='content2', time=1.2),
                ])),
                ('skipped', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='skipped', message='message2', content='content2', time=None),
                    UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='skipped', message='message3', content='content3', time=None),
                ])),
                ('failure', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='failure', message='message4', content='content4', time=1.23),
                    UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='failure', message='message4', content='content4', time=1.234),
                ])),
                ('error', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='error', message='message5', content='content5', time=1.2345),
                ])),
            ])),
            ('class2::test2', dict([
                ('success', list([
                    UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='success', message=None, content=None, time=None)
                ])),
                ('skipped', list([
                    UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='skipped', message=None, content=None, time=None)
                ])),
                ('failure', list([
                    UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='failure', message=None, content=None, time=None)
                ])),
                ('error', list([
                    UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='error', message=None, content=None, time=None)
                ])),
            ]))
        ])

        expected = CaseMessages([
            ('class1::test1', dict([
                ('success', defaultdict(list, [
                    ('content1', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1.0),
                        UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='success', message='message1', content='content1', time=1.1),
                    ])),
                    ('content2', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='success', message='message2', content='content2', time=1.2),
                    ]))
                ])),
                ('skipped', defaultdict(list, [
                    ('message2', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='skipped', message='message2', content='content2', time=None),
                    ])),
                    ('message3', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='skipped', message='message3', content='content3', time=None),
                    ]))
                ])),
                ('failure', defaultdict(list, [
                    ('content4', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='failure', message='message4', content='content4', time=1.23),
                        UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='failure', message='message4', content='content4', time=1.234),
                    ])),
                ])),
                ('error', defaultdict(list, [
                    ('content5', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=1, class_name='class1', test_name='test1', result='error', message='message5', content='content5', time=1.2345),
                    ])),
                ])),
            ])),
            ('class2::test2', dict([
                ('success', dict([
                    (None, list([
                        UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='success', message=None, content=None, time=None)
                    ])),
                ])),
                ('skipped', dict([
                    (None, list([
                        UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='skipped', message=None, content=None, time=None)
                    ])),
                ])),
                ('failure', dict([
                    (None, list([
                        UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='failure', message=None, content=None, time=None)
                    ])),
                ])),
                ('error', dict([
                    (None, list([
                        UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='error', message=None, content=None, time=None)
                    ])),
                ])),
            ]))
        ])

        actual = get_case_messages(results)

        self.assertEqual(expected, actual)

    def test_annotation_to_dict(self):
        annotation = Annotation(path='file1', start_line=123, end_line=123, annotation_level='notice', message='result-file1', title='1 out of 6 runs skipped: test1', raw_details='message2')
        self.assertEqual(dict(path='file1', start_line=123, end_line=123, annotation_level='notice', message='result-file1', title='1 out of 6 runs skipped: test1', raw_details='message2'), annotation.to_dict())
        annotation = Annotation(path='class2', start_line=0, end_line=0, annotation_level='failure', message='result-file1', title='1 out of 4 runs with error: test2 (class2)', raw_details=None)
        self.assertEqual(dict(path='class2', start_line=0, end_line=0, annotation_level='failure', message='result-file1', title='1 out of 4 runs with error: test2 (class2)'), annotation.to_dict())

    def test_get_annotation(self):
        messages = CaseMessages([
            ('class1::test1', dict([
                ('success', dict([
                    ('message1', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='success', message='message1', content=None, time=1.0)
                    ]))
                ])),
                ('skipped', dict([
                    ('message2', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name=None, test_name='test1', result='skipped', message='message2', content=None, time=1.0)
                    ]))
                ])),
                ('failure', dict([
                    ('message3', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='', test_name='test1', result='failure', message='message3', content=None, time=1.0)
                    ])),
                    ('message4', list([
                        UnitTestCase(result_file='result-file2', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='message4', content=None, time=1.0),
                        UnitTestCase(result_file='result-file3', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='message4', content=None, time=1.0)
                    ])),
                ])),
                ('error', dict([
                    ('message5', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='error', message='message6', content=None, time=1.0)
                    ]))
                ])),
            ])),
            ('class2::test2', dict([
                ('success', dict([
                    (None, list([
                        UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='success', message=None, content=None, time=None)
                    ])),
                ])),
                ('skipped', dict([
                    (None, list([
                        UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='skipped', message=None, content=None, time=None)
                    ])),
                ])),
                ('failure', dict([
                    (None, list([
                        UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='failure', message=None, content=None, time=None)
                    ])),
                ])),
                ('error', dict([
                    (None, list([
                        UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='error', message=None, content=None, time=None)
                    ])),
                ])),
            ]))
        ])

        self.assertEqual(Annotation(path='file1', start_line=123, end_line=123, annotation_level='notice', message='result-file1', title='1 out of 6 runs skipped: test1', raw_details='message2'), get_annotation(messages, 'class1::test1', 'skipped', 'message2', report_individual_runs=False))
        self.assertEqual(Annotation(path='file1', start_line=123, end_line=123, annotation_level='warning', message='result-file1\nresult-file2\nresult-file3', title='3 out of 6 runs failed: test1', raw_details='message3'), get_annotation(messages, 'class1::test1', 'failure', 'message3', report_individual_runs=False))
        self.assertEqual(Annotation(path='file1', start_line=123, end_line=123, annotation_level='warning', message='result-file1\nresult-file2\nresult-file3', title='3 out of 6 runs failed: test1 (class1)', raw_details='message4'), get_annotation(messages, 'class1::test1', 'failure', 'message4', report_individual_runs=False))
        self.assertEqual(Annotation(path='file1', start_line=123, end_line=123, annotation_level='failure', message='result-file1', title='1 out of 6 runs with error: test1 (class1)', raw_details='message5'), get_annotation(messages, 'class1::test1', 'error', 'message5', report_individual_runs=False))

        self.assertEqual(Annotation(path='class2', start_line=0, end_line=0, annotation_level='notice', message='result-file1', title='1 out of 4 runs skipped: test2 (class2)', raw_details=None), get_annotation(messages, 'class2::test2', 'skipped', None, report_individual_runs=False))
        self.assertEqual(Annotation(path='class2', start_line=0, end_line=0, annotation_level='warning', message='result-file1', title='1 out of 4 runs failed: test2 (class2)', raw_details=None), get_annotation(messages, 'class2::test2', 'failure', None, report_individual_runs=False))
        self.assertEqual(Annotation(path='class2', start_line=0, end_line=0, annotation_level='failure', message='result-file1', title='1 out of 4 runs with error: test2 (class2)', raw_details=None), get_annotation(messages, 'class2::test2', 'error', None, report_individual_runs=False))

    def test_get_annotation_report_individual_runs(self):
        messages = CaseMessages([
            ('class1::test1', dict([
                ('success', dict([
                    ('message1', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='success', message='message1', content=None, time=1.0)
                    ]))
                ])),
                ('skipped', dict([
                    ('message2', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name=None, test_name='test1', result='skipped', message='message2', content=None, time=None)
                    ]))
                ])),
                ('failure', dict([
                    ('message3', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='', test_name='test1', result='failure', message='message3', content=None, time=1.23)
                    ])),
                    ('message4', list([
                        UnitTestCase(result_file='result-file2', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='message4', content=None, time=1.234),
                        UnitTestCase(result_file='result-file3', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='message4', content=None, time=1.234)
                    ])),
                ])),
                ('error', dict([
                    ('message5', list([
                        UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='error', message='message6', content=None, time=1.2345)
                    ]))
                ])),
            ]))
        ])

        self.assertEqual(Annotation(path='file1', start_line=123, end_line=123, annotation_level='notice', message='result-file1', title='1 out of 6 runs skipped: test1', raw_details='message2'), get_annotation(messages, 'class1::test1', 'skipped', 'message2', report_individual_runs=True))
        self.assertEqual(Annotation(path='file1', start_line=123, end_line=123, annotation_level='warning', message='result-file1', title='1 out of 6 runs failed: test1', raw_details='message3'), get_annotation(messages, 'class1::test1', 'failure', 'message3', report_individual_runs=True))
        self.assertEqual(Annotation(path='file1', start_line=123, end_line=123, annotation_level='warning', message='result-file2\nresult-file3', title='2 out of 6 runs failed: test1 (class1)', raw_details='message4'), get_annotation(messages, 'class1::test1', 'failure', 'message4', report_individual_runs=True))
        self.assertEqual(Annotation(path='file1', start_line=123, end_line=123, annotation_level='failure', message='result-file1', title='1 out of 6 runs with error: test1 (class1)', raw_details='message5'), get_annotation(messages, 'class1::test1', 'error', 'message5', report_individual_runs=True))

    def test_get_annotations(self):
        results = UnitTestCaseResults([
            ('class1::test1', dict([
                ('success', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='success', message='success message', content='success content', time=1.0)
                ])),
                ('skipped', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name=None, test_name='test1', result='skipped', message='skip message', content='skip content', time=None)
                ])),
                ('failure', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 1', content='fail content 1', time=1.2),
                    UnitTestCase(result_file='result-file2', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 2', content='fail content 2', time=1.23),
                    UnitTestCase(result_file='result-file3', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 2', content='fail content 2', time=1.234)
                ])),
                ('error', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='error', message='error message', content='error content', time=1.2345)
                ])),
            ])),
            ('class2::test2', dict([
                ('success', list([
                    UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='success', message=None, content=None, time=None)
                ])),
                ('skipped', list([
                    UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='skipped', message=None, content=None, time=None)
                ])),
                ('failure', list([
                    UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='failure', message=None, content=None, time=None)
                ])),
                ('error', list([
                    UnitTestCase(result_file='result-file1', test_file=None, line=None, class_name='class2', test_name='test2', result='error', message=None, content=None, time=None)
                ])),
            ]))
        ])

        expected = [
            Annotation(
                annotation_level='warning',
                end_line=123,
                message='result-file1\nresult-file2\nresult-file3',
                path='file1',
                start_line=123,
                title='3 out of 6 runs failed: test1 (class1)',
                raw_details='fail content 1'
            ), Annotation(
                annotation_level='failure',
                end_line=123,
                message='result-file1',
                path='file1',
                start_line=123,
                title='1 out of 6 runs with error: test1 (class1)',
                raw_details='error content'
            ), Annotation(
                annotation_level='warning',
                end_line=0,
                message='result-file1',
                path='class2',
                start_line=0,
                title='1 out of 4 runs failed: test2 (class2)',
                raw_details=None
            ), Annotation(
                annotation_level='failure',
                end_line=0,
                message='result-file1',
                path='class2',
                start_line=0,
                title='1 out of 4 runs with error: test2 (class2)',
                raw_details=None
            ),
        ]

        annotations = get_annotations(results, report_individual_runs=False)

        self.assertEqual(expected, annotations)

    def test_get_annotations_report_individual_runs(self):
        results = UnitTestCaseResults([
            ('class1::test1', dict([
                ('success', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='success', message='success message', content='success content', time=1.0)
                ])),
                ('skipped', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name=None, test_name='test1', result='skipped', message='skip message', content='skip content', time=None)
                ])),
                ('failure', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 1', content='fail content 1', time=1.2),
                    UnitTestCase(result_file='result-file2', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 2', content='fail content 2', time=1.23),
                    UnitTestCase(result_file='result-file3', test_file='file1', line=123, class_name='class1', test_name='test1', result='failure', message='fail message 2', content='fail content 2', time=1.234)
                ])),
                ('error', list([
                    UnitTestCase(result_file='result-file1', test_file='file1', line=123, class_name='class1', test_name='test1', result='error', message='error message', content='error content', time=0.1)
                ])),
            ]))
        ])

        expected = [
            Annotation(
                annotation_level='warning',
                end_line=123,
                message='result-file1',
                path='file1',
                start_line=123,
                title='1 out of 6 runs failed: test1 (class1)',
                raw_details='fail content 1'
            ), Annotation(
                annotation_level='warning',
                end_line=123,
                message='result-file2\nresult-file3',
                path='file1',
                start_line=123,
                title='2 out of 6 runs failed: test1 (class1)',
                raw_details='fail content 2'
            ), Annotation(
                annotation_level='failure',
                end_line=123,
                message='result-file1',
                path='file1',
                start_line=123,
                title='1 out of 6 runs with error: test1 (class1)',
                raw_details='error content'
            )
        ]

        annotations = get_annotations(results, report_individual_runs=True)

        self.assertEqual(expected, annotations)

    def test_files(self):
        parsed = parse_junit_xml_files(['files/junit.gloo.elastic.spark.tf.xml',
                                        'files/junit.gloo.elastic.spark.torch.xml',
                                        'files/junit.gloo.elastic.xml',
                                        'files/junit.gloo.standalone.xml',
                                        'files/junit.gloo.static.xml',
                                        'files/junit.mpi.integration.xml',
                                        'files/junit.mpi.standalone.xml',
                                        'files/junit.mpi.static.xml',
                                        'files/junit.spark.integration.1.xml',
                                        'files/junit.spark.integration.2.xml']).with_commit('example')
        results = get_test_results(parsed, False)
        stats = get_stats(results)
        md = get_long_summary_md(stats)
        self.assertEqual(md, ('  10 files    10 suites   39m 1s :stopwatch:\n'
                              '217 tests 208 :heavy_check_mark:   9 :zzz: 0 :x:\n'
                              '373 runs  333 :heavy_check_mark: 40 :zzz: 0 :x:\n'
                              '\n'
                              'results for commit example\n'))

    def test_empty_file(self):
        parsed = parse_junit_xml_files(['files/empty.xml']).with_commit('a commit sha')
        results = get_test_results(parsed, False)
        stats = get_stats(results)
        md = get_long_summary_md(stats)
        self.assertEqual(md, ('1 files  1 suites   0s :stopwatch:\n'
                              '0 tests 0 :heavy_check_mark: 0 :zzz: 0 :x:\n'
                              '\n'
                              'results for commit a commit\n'))


if __name__ == '__main__':
    unittest.main()
