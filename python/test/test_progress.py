import unittest
from datetime import datetime, timezone

import mock

from publish.progress import Progress, ProgressLogger


class TestProgress(unittest.TestCase):
    def test_get_progress(self):
        progress = Progress(10)
        self.assertEqual('0 of 10', progress.get_progress())
        self.assertEqual('0 of 10', progress.get_progress())
        self.assertEqual('item', progress.observe('item'))
        self.assertEqual('1 of 10', progress.get_progress())
        self.assertEqual('1 of 10', progress.get_progress())
        self.assertEqual(1, progress.observe(1))
        self.assertEqual('2 of 10', progress.get_progress())
        self.assertEqual('2 of 10', progress.get_progress())
        self.assertEqual(1.2, progress.observe(1.2))
        self.assertEqual('3 of 10', progress.get_progress())
        self.assertEqual('3 of 10', progress.get_progress())
        obj = object()
        self.assertEqual(obj, progress.observe(obj))
        self.assertEqual('4 of 10', progress.get_progress())
        self.assertEqual('4 of 10', progress.get_progress())

    def test_get_progress_thousands(self):
        progress = Progress(12345)
        self.assertEqual('0 of 12 345', progress.get_progress())
        for _ in range(12340):
            self.assertEqual('item', progress.observe('item'))
        self.assertEqual('12 340 of 12 345', progress.get_progress())


class TestProgressLogger(unittest.TestCase):
    def test(self):
        progress = Progress(10)
        logger = mock.MagicMock(info=mock.Mock())
        plogger = ProgressLogger(progress, 60, 'progress: {progress} in {time}', logger)
        try:
            ts = datetime(2022, 6, 1, 12, 34, 56, tzinfo=timezone.utc)
            with mock.patch('publish.progress.datetime', utcnow=mock.Mock(return_value=ts)):
                plogger.start()
            logger.info.assert_not_called()

            progress.observe('item')
            logger.info.assert_not_called()

            ts = datetime(2022, 6, 1, 12, 35, 00, tzinfo=timezone.utc)
            with mock.patch('publish.progress.datetime', utcnow=mock.Mock(return_value=ts)):
                plogger._log_progress()
            self.assertEqual([mock.call('progress: 1 of 10 in 4 seconds')], logger.info.call_args_list)
            logger.info.reset_mock()

            progress.observe('item')
            progress.observe('item')
            logger.info.assert_not_called()

            ts = datetime(2022, 6, 1, 12, 40, 00, tzinfo=timezone.utc)
            with mock.patch('publish.progress.datetime', utcnow=mock.Mock(return_value=ts)):
                plogger._log_progress()
            self.assertEqual([mock.call('progress: 3 of 10 in 5 minutes and 4 seconds')], logger.info.call_args_list)
            logger.info.reset_mock()
        finally:
            ts = datetime(2022, 6, 1, 12, 41, 23, tzinfo=timezone.utc)
            with mock.patch('publish.progress.datetime', utcnow=mock.Mock(return_value=ts)):
                plogger.finish('finished: {observations} of {items} in {duration}')
            self.assertEqual([mock.call('finished: 3 of 10 in 6 minutes and 27 seconds')], logger.info.call_args_list)
            logger.info.reset_mock()

        self.assertEqual('6 minutes and 27 seconds', plogger.duration)
