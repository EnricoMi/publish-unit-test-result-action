import contextlib
from datetime import datetime
from logging import Logger
from threading import Timer
from typing import Generic, TypeVar, Optional, Callable, Type, Any

import humanize

from publish import punctuation_space

T = TypeVar('T')


@contextlib.contextmanager
def progress_logger(items: int,
                    interval_seconds: int,
                    progress_template: str,
                    finish_template: Optional[str],
                    logger: Logger,
                    progress_item_type: Type[T] = Any) -> Callable[[T], T]:
    progress = Progress[progress_item_type](items)
    plogger = ProgressLogger(progress, interval_seconds, progress_template, logger).start()
    try:
        yield progress.observe
    finally:
        plogger.finish(finish_template)


class Progress(Generic[T]):
    def __init__(self, items: int):
        self.items = items
        self.observations = 0

    def observe(self, observation: T) -> T:
        self.observations = self.observations + 1
        return observation

    def get_progress(self) -> str:
        return '{observations:,} of {items:,}'.format(
            observations=self.observations, items=self.items
        ).replace(',', punctuation_space)


class ProgressLogger:
    def __init__(self, progress: Progress, interval_seconds: int, template: str, logger: Logger):
        self._progress = progress
        self._interval_seconds = interval_seconds
        self._template = template
        self._logger = logger

        self._start = None
        self._duration = None
        self._timer = self._get_progress_timer()

    def start(self) -> 'ProgressLogger':
        self._start = datetime.utcnow()
        self._timer.start()
        return self

    def finish(self, template: Optional[str] = None):
        self._duration = datetime.utcnow() - self._start
        self._start = None
        self._timer.cancel()

        if template:
            self._logger.info(template.format(items=self._progress.items,
                                              observations=self._progress.observations,
                                              duration=self.duration))

    @property
    def duration(self) -> str:
        return humanize.precisedelta(self._duration)

    def _get_progress_timer(self):
        timer = Timer(self._interval_seconds, self._log_progress)
        timer.setDaemon(daemonic=True)
        return timer

    def _log_progress(self):
        if self._start is None:
            return

        delta = datetime.utcnow() - self._start
        self._logger.info(self._template.format(progress=self._progress.get_progress(), time=humanize.precisedelta(delta)))
        self._timer = self._get_progress_timer()
        self._timer.start()
