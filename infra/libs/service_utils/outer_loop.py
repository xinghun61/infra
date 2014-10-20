# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Outer loop for services that run short lived tasks."""

import collections
import logging
import time

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


def loop(task, sleep_timeout, duration=None, max_errors=None):
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

  Returns:
    @returns LoopResults.
  """
  deadline = None if duration is None else (time.time() + duration)
  errors_left = max_errors
  failed = False
  loop_count = 0
  error_count = 0
  try:
    while True:
      # Log that new attempt is starting.
      start = time.time()
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
        attempt_success = task()
      except KeyboardInterrupt:
        raise
      except Exception:
        LOGGER.exception('Uncaught exception in the task')
      finally:
        LOGGER.info('End loop %d (%f sec)', loop_count, time.time() - start)
        LOGGER.info('-------------------')

      # Reset error counter on success, or abort on too many errors.
      if attempt_success:
        errors_left = max_errors
      else:
        error_count += 1
        if errors_left is not None:
          errors_left -= 1
          if not errors_left:
            failed = True
            LOGGER.warn(
                'Too many consecutive errors (%d), stopping.', max_errors)
            break

      # Sleep before trying again.
      # TODO(vadimsh): Make sleep timeout dynamic.
      now = time.time()
      timeout = sleep_timeout()
      if deadline and now + timeout >= deadline:
        when = now - deadline
        if when > 0:
          LOGGER.info('Deadline reached %.1f sec ago, stopping.', when)
        else:
          LOGGER.info('Deadline is in %.1f sec, stopping now', -when)
        break
      LOGGER.debug('Sleeping %.1f sec', timeout)
      time.sleep(timeout)

      loop_count += 1
  except KeyboardInterrupt:
    LOGGER.warn('Stopping due to KeyboardInterrupt')

  return LoopResults(not failed, error_count)


def add_argparse_options(parser):  # pragma: no cover
  """Adds loop related options to an argparse.ArgumentParser."""
  parser.add_argument('--duration', metavar='SEC', type=int,
                      help=('How long to run the service loop '
                            '(default: forever)'))
  parser.add_argument('--max_errors', metavar='COUNT', type=int,
                      help=('Number of consecutive errors after which the '
                            'service loop is aborted (default: +inf)'))


def process_argparse_options(opts):  # pragma: no cover
  """Handles argparse options added in 'add_argparse_options'.

  Returns:
    @returns Dict with options that can be passed as kwargs to outer_loop.
  """
  return {
    'duration': opts.duration,
    'max_errors': opts.max_errors,
  }
