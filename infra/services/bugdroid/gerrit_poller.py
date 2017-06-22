# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Poller and support classes for git repositories with a gerrit interface.

This module can poll git repositories for commit activity without requiring a
local git checkout.

(Based largely on the structure of chrome.bugdroid.git_poller.)
"""
# TODO(mmoss): Refactor common methods with gitiles_poller.

import collections
import datetime
import json
import logging
import os
import sys

import infra.services.bugdroid.gob_helper as gob_helper
import infra.services.bugdroid.poller_handlers as poller_handlers
from infra.services.bugdroid.poll import Poller


DEFAULT_LOGGER = logging.getLogger(__name__)
DEFAULT_LOGGER.addHandler(logging.NullHandler())


class FileBitmap(object):
  """File-backed bitmap (automatically flushes each change)."""

  def __init__(self, filepath, count):
    self.count = count
    # Make sure the file has at least as many bits as requested.
    byte_count = (self.count + 8) / 8
    # Initialize the backing store if necessary.
    if not os.path.exists(filepath):
      DEFAULT_LOGGER.debug('Creating FileBitmap "%s" of %d bytes', filepath,
                           byte_count)
      with open(filepath, 'wb') as fn:
        fn.truncate(byte_count)
    file_size = os.stat(filepath).st_size
    if file_size != byte_count:
      # TODO(mmoss): This might be destructive, so backup the existing file?
      DEFAULT_LOGGER.info('Resizing "%s" from %d to %d bytes.', filepath,
                          file_size, byte_count)
      with open(filepath, 'r+b') as fn:
        fn.truncate(byte_count)
    # Hold it open for editing.
    self.bitmap_file = open(filepath, 'r+b')
    self.bitmap_file.flush()

  def __del__(self):
    if self.bitmap_file:
      self.bitmap_file.close()

  def _GetFileByte(self, index):
    """Get the byte from the file containing the given bit."""
    if index < 0 or index >= self.count:
      raise IndexError('%d is outside range [0, %d]' % (index, self.count - 1))
    byte_index = index / 8
    bit_offset = index % 8
    bit_mask = 1 << bit_offset
    self.bitmap_file.seek(byte_index)
    return byte_index, bit_mask, ord(self.bitmap_file.read(1))

  def CheckBit(self, index):
    _, bit_mask, byte = self._GetFileByte(index)
    return bool(byte & bit_mask)

  def SetBit(self, index):
    byte_index, bit_mask, byte = self._GetFileByte(index)
    byte = byte | bit_mask
    self.bitmap_file.seek(byte_index)
    self.bitmap_file.write(chr(byte))
    self.bitmap_file.flush()


class GerritPoller(Poller):
  """Poller for monitoring commits to a gerrit host using the REST API.

  Args:
    host_url: The url of the gerrit host to poll.
    poller_id: ID for the poller instance.
    commits_since: datetime() of the oldest commits to look for.
  """

  def __init__(self, host_url, poller_id,
               commits_since=None, interval_in_minutes=3,
               setup_refresh_interval_minutes=0, logger=None, run_once=False,
               with_paths=True, with_diffs=False, datadir=None,
               git_projects=None):
    Poller.__init__(self, interval_in_minutes, setup_refresh_interval_minutes,
                    run_once)
    self.logger = logger or DEFAULT_LOGGER
    self.gerrit = gob_helper.GerritHelper(host_url, self.logger, git_projects)
    self.poller_id = poller_id
    self.handlers = []
    self.with_paths = with_paths
    self.with_diffs = with_diffs
    self.__last_seen = None
    self.last_seen_fn = os.path.join(datadir or '', '%s.txt' % self.poller_id)
    # Initializes last_seen with |commits_since|, or stored value, or now().
    self.last_seen = commits_since
    self.logger.info('Polling changes since: %s', self.last_seen)
    seen_bitmap_fn = os.path.join(datadir or '', '%s.seen' % self.poller_id)
    # TODO(mmoss): Hopefully 10,000,000 changes is enough for quite a while
    # (currently <300,000), and hopefully gerrit just numbers the changes in
    # small increments.
    self.seen_bitmap = FileBitmap(seen_bitmap_fn, 10000000)

  @property
  def last_seen(self):
    return self.__last_seen

  @last_seen.setter
  def last_seen(self, timestamp):
    # Initialize the stored value.
    if not os.path.exists(self.last_seen_fn):
      self.logger.debug('Creating "last seen" file: %s', self.last_seen_fn)
      with open(self.last_seen_fn, 'w') as f:
        f.write(timestamp or
                self.gerrit.GenerateTimeStamp(datetime.datetime.utcnow()))
    # Default to the stored value.
    if not self.__last_seen:
      with open(self.last_seen_fn, 'r') as f:
        self.__last_seen = self.gerrit.ParseTimeStamp(f.read().strip())
    # None is ignored, and can be used as a "default initializer".
    if timestamp is None:
      self.logger.debug('Ignoring None timestamp.')
      return
    # Convert the timestamp to a datetime() if it's not already.
    try:
      timestamp = self.gerrit.ParseTimeStamp(timestamp)
    except ValueError:
      self.logger.warning('Ignoring unsupported timestamp: %s', timestamp)
      return
    if timestamp == self.__last_seen:
      return
    # Looks like a good, new value, so store and set it.
    with open(self.last_seen_fn, 'w') as f:
      f.write(self.gerrit.GenerateTimeStamp(timestamp))
    self.__last_seen = timestamp

  def _ProcessGitLogEntry(self, log_entry):
    if log_entry.ignored:
      self.logger.debug('Not processing ignored commit %s.', log_entry.commit)
      self.commits_metric.increment(
          {'poller': 'gerrit', 'project': self.poller_id, 'status': 'ignored'})
      return
    for handler in self.handlers:
      try:
        handler.ProcessLogEntry(log_entry)
      except Exception as e:
        # Log it here so that we see where it's breaking.
        self.logger.exception('Uncaught Exception in %s', handler)
        self.commits_metric.increment(
            {'poller': 'gerrit', 'project': self.poller_id, 'status': 'error'})
        # Some handlers aren't that important, but other ones should always
        # succeed, and should abort processing if they don't.
        if handler.must_succeed:
          raise e
        self.logger.info('Handler is not fatal. Continuing.')
        continue
      else:
        self.commits_metric.increment(
            {'poller': 'gerrit', 'project': self.poller_id,
             'status': 'success'})

  def add_handler(self, handler):
    if not isinstance(handler, poller_handlers.BasePollerHandler):
      raise TypeError('%s doesn\'t accept handlers of type %s' %
                      self.__class__.__name__, type(handler))
    self.handlers.append(handler)

  def execute(self):
    extra_fields = ['CURRENT_COMMIT', 'CURRENT_REVISION']
    if self.with_paths:
      extra_fields.append('CURRENT_FILES')

    # Set a hard limit on the number of commits to process, so it doesn't
    # accidentally do something crazy like try to process all commits since the
    # beginning of time.
    max_changes = 1000

    start_since = self.last_seen

    # TODO(mmoss): Does this need with_diffs handling?
    # Find commits since the last_seen time.
    entries, more = self.gerrit.GetLogEntries(since=start_since,
                                              limit=max_changes,
                                              fields=extra_fields)
    self.logger.debug('Found %s commits since %s.', len(entries), start_since)
    if more:
      self.logger.warning('Not processing all commits since %s '
                          '(limit: %d).', start_since, max_changes)

    # Gerrit output is sorted by the last update time, most recent to oldest, so
    # process in reverse order to make sure self.last_seen is always older than
    # any unprocessed items.
    for entry in reversed(entries):
      if self.seen_bitmap.CheckBit(entry.number):
        self.logger.debug('Rejecting %s (%s), which was previously seen.',
                          entry.commit, entry.number)
        self.commits_metric.increment(
            {'poller': 'gerrit', 'project': self.poller_id, 'status': 'seen'})
        continue
      # There seems to be some bug in gerrit's "since" param handling, where it
      # sometimes returns changes older than "since" (.5 seconds or more too
      # old), so manually verify and reject anything like that, otherwise
      # bugdroid might repeatedly process the same commits.
      if entry.update_datetime <= start_since:
        self.logger.debug('Rejecting %s, not newer than requested "since". '
                          '(%s < %s)' % (entry.commit, entry.update_datetime,
                                         start_since))
        self.commits_metric.increment(
            {'poller': 'gerrit', 'project': self.poller_id, 'status': 'old'})
        continue
      try:
        self._ProcessGitLogEntry(entry)
      except Exception:
        self.logger.error('Aborting processing of commits.')
        break

      # Finished processing this commit. Mark it as seen and save its timestamp
      # as the new query starting point.
      self.seen_bitmap.SetBit(entry.number)
      self.last_seen = entry.update_datetime


