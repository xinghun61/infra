# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Poller and support classes for git repositories with a gitiles interface.

This module can poll git repositories for commit activity without requiring a
local git checkout. Some functionality is limited by the current gitiles JSON
API, though that will hopefully be expanded in the near future.

(Based largely on the structure of chrome.bugdroid.svn_poller.)

Sample Usage:
  p = gitiles_poller.GitilesPoller(
    git_url='https://chromium.googlesource.com/chromium/src.git',
    poller_id='chromium_src_poller',
    refs_regex=['refs/heads/git-svn'])
  p.add_handler(poller_handlers.EmailPollerHandler(must_succeed=True))
  p.start()
"""

import collections
import json
import logging
import os
import sys

import infra.services.bugdroid.gob_helper as gob_helper
import infra.services.bugdroid.poller_handlers as poller_handlers
from infra.services.bugdroid.poll import Poller


DEFAULT_LOGGER = logging.getLogger(__name__)
DEFAULT_LOGGER.addHandler(logging.NullHandler())


class HaltProcessing(Exception):
  pass


class FileDict(collections.MutableMapping):
  """A JSON file-backed dictionary for poller metadata."""

  def __init__(self, backing_file, *args, **kwargs):
    self.logger = DEFAULT_LOGGER
    self.__backingstore = backing_file
    self.logger.debug('Using backing store: %s', self.__backingstore)
    self.__store = None
    self._LoadStore()
    # Call update on the __store, rather than on self, so it doesn't try to
    # write out each key as it's added.
    self.__store.update(dict(*args, **kwargs))
    # Now write it out in case anything changed.
    self._SaveStore()

  def __getitem__(self, key):
    return self.__store[key]

  def __setitem__(self, key, value):
    if self.__store[key] != value:
      self.__store[key] = value
      self._SaveStore()

  def __delitem__(self, key):
    del self.__store[key]
    self._SaveStore()

  def __iter__(self):
    return iter(self.__store)

  def __len__(self):
    return len(self.__store)

  # TODO(mmoss): Generalize backend storage to allow, for instance, either
  # local files or cloud storage objects (for running on appengine).
  def _OpenStore(self, mode):
    if not os.path.exists(self.__backingstore):
      # Automatically create a JSON stub file if it doesn't exist.
      self.logger.debug('Creating backing store: %s', self.__backingstore)
      fp = open(self.__backingstore, 'w')
      fp.write('{}')
      fp.close()
    fp = open(self.__backingstore, mode)
    return fp

  def _LoadStore(self):
    fp = self._OpenStore('r')
    tmp = json.load(fp=fp)
    fp.close()
    self.__store = tmp or {}

  def _SaveStore(self):
    fp = self._OpenStore('w')
    json.dump(self.__store, fp)
    fp.close()

  def BatchUpdate(self, commits):
    """Update method that avoids writing the file on every item change."""
    dirty = False
    for key, value in commits.iteritems():
      if (key not in self.__store) or (self.__store.get(key) != value):
        self.__store[key] = value
        dirty = True
    if dirty:
      self._SaveStore()


class GitilesPoller(Poller):
  """Poller for monitoring changes to a git repository using the gitiles web UI.

  Args:
    git_url: The url of the repository to poll.
    poller_id: ID for the poller instance.
    refs_regex: Which remote refs to include when polling for changes, specified
      as a list of regexes. Default is to only poll remote HEAD.
    start_commits: Dict of "remote_ref: commit_hash" specifying the commit to
      start polling at for each remote ref (i.e. parents of these commits on
      these branches have already been processed). If the commit is empty, any
      previously stored commit for that branch will be cleared.
  """

  def __init__(self, git_url, poller_id, refs_regex=None,
               start_commits=None, interval_in_minutes=3,
               setup_refresh_interval_minutes=0, logger=None, run_once=False,
               with_paths=True, with_diffs=False, paths_regex=None,
               filter_regex=None, datadir=None):
    Poller.__init__(self, interval_in_minutes, setup_refresh_interval_minutes,
                    run_once)
    self.logger = logger or DEFAULT_LOGGER
    self.gitiles = gob_helper.GitilesHelper(git_url, self.logger)
    self.refs_regex = refs_regex or ['HEAD']
    self.poller_id = poller_id
    self.handlers = []
    self.with_paths = with_paths
    self.with_diffs = with_diffs
    self.paths_regex = paths_regex
    self.filter_regex = filter_regex

    fn = os.path.join(datadir or '', '%s.json' % self.poller_id)
    self.last_commits = FileDict(fn)
    self.start_commits = start_commits or {}

    # An empty start commit means any previous setting should be cleared.
    empty_keys = [k for k, v in self.start_commits.iteritems() if not v]
    for key in empty_keys:
      if key in self.last_commits:
        del self.last_commits[key]
      del self.start_commits[key]

    # Store any previously unseen branch:commit settings.
    new_commits = self._FindNewRefs(self.start_commits)
    self.last_commits.BatchUpdate(new_commits)

    for key in new_commits.iterkeys():
      del self.start_commits[key]
    # Anything left in start_commits has a previous entry in last_commits.
    # Handle those as part of the regular commit update processing (see
    # execute()) to determine if the start_commits are more recent than the
    # last_commits, and thus should become the new last_commits.

  def _FindNewRefs(self, refs):
    """Filter a ref:commit dict for refs that haven't been seen yet."""
    new_refs = {}
    for key in refs.iterkeys():
      if key not in self.last_commits:
        new_refs[key] = refs[key]
    return new_refs

  def _ProcessGitLogEntry(self, log_entry):
    self.logger.debug('Received git log entry\n%s' % log_entry.msg)
    if log_entry.ignored:
      self.logger.debug('Not processing ignored commit %s.', log_entry.commit)
      return
    for handler in self.handlers:
      try:
        handler.ProcessLogEntry(log_entry)
      except HaltProcessing as e:
        self.logger.exception('Halting in %s', handler)
        raise e
      except Exception as e:
        # Log it here so that we see where it's breaking.
        self.logger.exception('Uncaught Exception in %s', handler)
        # Some handlers aren't that important, but other ones should always
        # succeed, and should abort processing if they don't.
        if handler.must_succeed:
          raise e
        self.logger.info('Handler is not fatal. Continuing.')
        continue

  def _ProcessRefs(self, refs, filter_refs=None, store_only=False):
    """Detect changes to watched branches and process new commits.

    Args:
      refs: dict of ref commits to compare against stored values.
      filter_refs: dict of ref filters (e.g. upstream refs) to use to filter out
        unwanted commits from each ref.
      store_only: If the refs have updated to a later commit, just store that
        new commit, don't process all the intervening commits. Useful to
        "fast-forward" baseline commits.
    """
    filter_refs = filter_refs or {}
    maxentries = 1000 if self.with_paths else 3000
    # Check for changes to watched branches.
    for key in refs.iterkeys():
      if refs[key] == self.last_commits[key]:
        continue
      self.logger.debug('"%s" branch changed: %s -> %s', key,
                        self.last_commits[key], refs[key])
      # Find commits between the stored commit and the current one. If the
      # stored commit is newer, or not an ancestor, this should be empty.
      entries, nextcommit = self.gitiles.GetLogEntries(
          key, ancestor=self.last_commits[key], limit=maxentries,
          with_paths=self.with_paths, with_diffs=self.with_diffs,
          filter_paths=self.paths_regex, filter_ref=filter_refs.get(key))
      if not entries:
        continue
      if store_only:
        self.last_commits[key] = refs[key]
        continue

      if nextcommit:
        self.logger.warning('%s: Not processing all commits from %s to %s '
                            '(limit: %d)', key, self.last_commits[key],
                            refs[key], maxentries)
      for entry in reversed(entries):
        # This shouldn't ever happen, but just to be safe.
        if self.last_commits[key] == entry.commit:
          self.logger.error('Attempted reprocessing of commit %s', entry.commit)
          continue

        try:
          self._ProcessGitLogEntry(entry)
        except HaltProcessing:
          self.logger.error('HaltProcessing caught - Terminating program')
          sys.exit(1)
        except Exception:
          self.logger.error('Aborting processing of "%s" commits.', key)
          break

        # Finished processing this commit. Save it as the new starting point.
        self.last_commits[key] = entry.commit

  def add_handler(self, handler):
    if isinstance(handler, poller_handlers.BasePollerHandler):
      self.handlers.append(handler)
      handler.logger = self.logger
    else:
      self.logger.error('%s doesn\'t accept handlers of type %s',
                        self.__class__.__name__, type(handler))

  def execute(self):
    # Pocess remaining initialization commits. Most likely these are just older,
    # baseline commits, and the poller has already processed well past them, but
    # it's possible that someone updated the baseline to something after what
    # the poller last saw (e.g. if the poller was offline for a while, but they
    # don't want to reprocess everything that was missed).
    if self.start_commits:
      self.logger.debug('Processing leftover start_commits: %s',
                        self.start_commits)
      self._ProcessRefs(self.start_commits, store_only=True)
      self.start_commits = {}

    # Get updated dict of watched branches and commits.
    refs, filters = self.gitiles.GetRefs(self.refs_regex, self.filter_regex)
    new_refs = self._FindNewRefs(refs)
    # TODO(mmoss): Find the branch point for each of these refs and use that as
    # each one's last_commit, to ensure all commits on a branch are processed.
    # For now, this will just process commits from this point on (which, if run
    # often enough, should catch most commits).
    if new_refs:
      self.logger.debug('Found new refs: %s', new_refs)
      self.last_commits.BatchUpdate(new_refs)

    self._ProcessRefs(refs, filters)
