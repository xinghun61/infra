# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Outer loop for services that run short lived tasks."""

import collections
import logging
import sys
import time

from infra_libs import ts_mon
import infra_libs

LOGGER = logging.getLogger(__name__)

LoopResults = collections.namedtuple(
    'LoopResults',
    [
      # True on no errors or if all failed attempts were successfully retried.
      'success',
      # Total number of errors seen (some may have been fixed with retries).
      'error_count',
    ],
)


def loop(task, sleep_timeout, duration=None, max_errors=None, time_mod=time):
  """Runs the task in a loop for a given duration.

  Handles and logs all uncaught exceptions. ``task`` callback should return True
  on success, and False (or raise an exception) in error.

  Doesn't leak any exceptions (including KeyboardInterrupt).

  Args:
    @param task: Callable with no arguments returning True or False.
    @param sleep_timeout: A function returning how long to sleep between task
                          invocations (sec), called once per loop.
    @param duration: How long to run the loop (sec), or None for forever.
    @param max_errors: Max number of consecutive errors before loop aborts.
    @param time_mod: Object implementing the interface of the standard `time`
                     module. Used by tests to mock time.time and time.sleep.

  Returns:
    @returns LoopResults.
  """
  deadline = None if duration is None else (time_mod.time() + duration)
  errors_left = max_errors
  seen_success = False
  failed = False
  loop_count = 0
  error_count = 0
  count_metric = ts_mon.CounterMetric('proc/outer_loop/count')
  success_metric = ts_mon.BooleanMetric('proc/outer_loop/success')
  durations_metric = ts_mon.DistributionMetric('proc/outer_loop/durations')
  try:
    while True:
      # Log that new attempt is starting.
      start = time_mod.time()
      LOGGER.info('-------------------')
      if deadline is not None:
        LOGGER.info(
            'Begin loop %d (%.1f sec to deadline)',
            loop_count, deadline - start)
      else:
        LOGGER.info('Begin loop %d', loop_count)

      # Do it. Abort if number of consecutive errors is too large.
      attempt_success = False
      try:
        with ts_mon.ScopedIncrementCounter(count_metric) as cm:
          attempt_success = task()
          if not attempt_success:  # pragma: no cover
            cm.set_failure()       # Due to branch coverage bug in coverage.py
      except KeyboardInterrupt:
        raise
      except Exception:
        LOGGER.exception('Uncaught exception in the task')
      finally:
        elapsed = time_mod.time() - start
        LOGGER.info('End loop %d (%f sec)', loop_count, elapsed)
        durations_metric.add(elapsed)
        LOGGER.info('-------------------')

      # Reset error counter on success, or abort on too many errors.
      if attempt_success:
        seen_success = True
        errors_left = max_errors
      else:
        error_count += 1
        if errors_left is not None:
          errors_left -= 1
          if errors_left <= 0:
            failed = True
            LOGGER.warn(
                'Too many consecutive errors (%d), stopping.', max_errors)
            break

      # Sleep before trying again.
      # TODO(vadimsh): Make sleep timeout dynamic.
      now = time_mod.time()
      timeout = sleep_timeout()
      if deadline is not None and now + timeout >= deadline:
        when = now - deadline
        if when > 0:
          LOGGER.info('Deadline reached %.1f sec ago, stopping.', when)
        else:
          LOGGER.info('Deadline is in %.1f sec, stopping now', -when)
        break
      LOGGER.debug('Sleeping %.1f sec', timeout)
      time_mod.sleep(timeout)

      loop_count += 1
  except KeyboardInterrupt:
    seen_success = True
    LOGGER.warn('Stopping due to KeyboardInterrupt')

  success = not failed and seen_success
  success_metric.set(success)
  return LoopResults(success, error_count)


def add_argparse_options(parser):  # pragma: no cover
  """Adds loop related options to an argparse.ArgumentParser."""
  parser.add_argument('--duration', metavar='SEC', type=int,
                      help=('How long to run the service loop '
                            '(default: forever)'))
  parser.add_argument('--max-errors', metavar='COUNT', type=int,
                      help=('Number of consecutive errors after which the '
                            'service loop is aborted (default: +inf)'))
  parser.add_argument('--max_errors', metavar='COUNT', type=int,
                      help=('Deprecated. See "--max-errors".'))


def process_argparse_options(opts):  # pragma: no cover
  """Handles argparse options added in 'add_argparse_options'.

  Returns:
    @returns Dict with options that can be passed as kwargs to outer_loop.
  """
  return {
    'duration': opts.duration,
    'max_errors': opts.max_errors,
  }


class Application(infra_libs.BaseApplication):  # pragma: no cover
  """A top-level Application class for apps that use outer_loop.

  Subclasses must implement the task() and sleep_timeout() methods.
  See the docs for infra_libs.BaseApplication for more details.

  Usage::

    class MyApplication(outer_loop.Application):
      def task(self):
        # Do stuff
        return True

      def sleep_timeout(self):
        return 60

    if __name__ == '__main__':
      MyApplication().run()
  """

  def add_argparse_options(self, parser):
    super(Application, self).add_argparse_options(parser)
    add_argparse_options(parser)

  def process_argparse_options(self, opts):
    super(Application, self).process_argparse_options(opts)
    process_argparse_options(opts)

  def task(self):
    """Called every loop iteration to do the work.

    Should return True on success, and False (or raise an exception) in error.
    """
    raise NotImplementedError

  def sleep_timeout(self):
    """Returns how long to sleep between task invocations (sec).

    Called once per loop.
    """
    raise NotImplementedError

  def main(self, opts):
    result = loop(
        task=self.task,
        sleep_timeout=self.sleep_timeout,
        duration=opts.duration,
        max_errors=opts.max_errors)

    return 0 if result.success else 1
