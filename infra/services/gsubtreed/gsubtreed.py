# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import posixpath
import sys
import threading

from infra.libs.git2 import CalledProcessError
from infra.libs.git2 import INVALID
from infra.libs.git2 import config_ref
from infra.libs.git2 import repo

from infra.services.gnumbd.gnumbd import FOOTER_PREFIX
from infra.services.gnumbd.gnumbd import GIT_SVN_ID
from infra.services.gnumbd.gnumbd import PUSH_TIMEOUT

LOGGER = logging.getLogger(__name__)

MIRRORED_FROM = FOOTER_PREFIX + 'Mirrored-From'
MIRRORED_COMMIT = FOOTER_PREFIX + 'Mirrored-Commit'


################################################################################
# ConfigRef
################################################################################

class GsubtreedConfigRef(config_ref.ConfigRef):
  CONVERT = {
    'interval': lambda self, val: float(val),

    'base_url': lambda self, val: str(val) if val else self.repo.url,
    'enabled_refglobs': lambda self, val: map(str, list(val)),
    # normpath to avoid trailing/double-slash errors.
    'enabled_paths': lambda self, val: map(posixpath.normpath, map(str, val)),
  }
  DEFAULTS = {
    'interval': 5.0,

    # The base URL is the url relative to which all mirror repos are assumed to
    # exist. For example, if you mirror the path 'bob', and base_url is
    # https://host.domain.tld/main_repo, then it would assume that the mirror
    # for the bob subtree is https://host.domain.tld/main_repo/bob.
    #
    # By default, base_url is set to the repo that gsubtreed is processing
    'base_url': None,
    'enabled_refglobs': ['refs/heads/*'],
    'enabled_paths': [],
  }
  REF = 'refs/gsubtreed-config/main'



################################################################################
# Core functionality
################################################################################


class Pusher(threading.Thread):
  # Modified by testing code. Makes this object do all the work in 'get_result'
  # (instead of a separate thread). That way the order of tasks is deterministic
  # (and defined by the order 'get_result' calls).
  FAKE_THREADING = False

  def __init__(self, name, dest_repo, pushspec):
    super(Pusher, self).__init__()
    self._name = name
    self._repo = dest_repo
    self._pushspec = pushspec

    self._success = False
    self._output = None

  def run(self):
    if not self.FAKE_THREADING:  # pragma: no cover
      self._push()

  def get_result(self):
    self.join()
    if self.FAKE_THREADING:  # pragma: no cover
      self._push()
    log = logging.info if self._success else logging.error
    prefix = 'Completed' if self._success else 'FAILED'
    log('%s push for %r', prefix, self._name)
    if self._output:
      log(self._output)  # pragma: no cover
    return self._success

  def _push(self):
    try:
      self._output = self._repo.fast_forward_push(
          self._pushspec, include_err=True, timeout=PUSH_TIMEOUT)
      self._success = True
    except CalledProcessError as cpe:  # pragma: no cover
      self._output = str(cpe)


def process_path(path, origin_repo, config):
  base_url = config['base_url']
  mirror_url = '[FILE-URL]' if base_url.startswith('file:') else origin_repo.url

  subtree_repo = repo.Repo(posixpath.join(base_url, path))
  subtree_repo.repos_dir = origin_repo.repos_dir
  subtree_repo.reify(share_from=origin_repo)
  subtree_repo.run('fetch', stdout=sys.stdout, stderr=sys.stderr)
  subtree_repo_push = {}

  synthed_count = 0

  success = True

  for glob in config['enabled_refglobs']:
    for ref in origin_repo.refglob(glob):
      LOGGER.info('processing ref %s', ref)

      # The last thing that was pushed to the subtree_repo
      synth_parent = subtree_repo[ref.ref].commit

      processed = INVALID
      if synth_parent is not INVALID:
        f = synth_parent.data.footers
        if MIRRORED_COMMIT not in f:
          logging.warn('Getting data from extra_footers. This information is'
                       'only as trustworthy as the ACLs.')
          f = synth_parent.extra_footers()
        if MIRRORED_COMMIT not in f:
          success = False
          logging.error('Could not find footers for synthesized commit %r',
                        synth_parent.hsh)
          continue
        processed_commit = f[MIRRORED_COMMIT][0]
        processed = origin_repo.get_commit(processed_commit)
        logging.info('got processed commit %s: %r', processed_commit, processed)

        if processed is INVALID:
          success = False
          logging.error('Subtree mirror commit %r claims to mirror commit %r, '
                        'which doesn\'t exist in the origin repo. Halting.',
                        synth_parent.hsh, processed_commit)
          continue

      LOGGER.info('starting with tree %r', synth_parent.data.tree)

      for commit in origin_repo[processed.hsh].to(ref, path):
        LOGGER.info('processing commit %s', commit)
        obj_name = '{.hsh}:{}'.format(commit, path)
        typ = origin_repo.run('cat-file', '-t', obj_name).strip()
        if typ != 'tree':
          LOGGER.warn('path %r is not a tree in commit %s', path, commit)
          continue
        dir_tree = origin_repo.run('rev-parse', obj_name).strip()

        LOGGER.info('found new tree %r', dir_tree)

        # Remove git-svn-id, Cr-Commit-Position and Cr-Branched-From
        # Replace original Cr- footers
        # to indicate them as the /original/ values.
        footers = [
          (GIT_SVN_ID, None),
        ]
        for key, val in commit.data.footers.iteritems():
          if key.startswith(FOOTER_PREFIX):
            footers += [
              (key, None),
              (key.replace(FOOTER_PREFIX, FOOTER_PREFIX + 'Original-', 1), val),
            ]

        footers += [
          (MIRRORED_FROM, [mirror_url]),
          (MIRRORED_COMMIT, [commit.hsh]),
        ]

        synthed_count += 1
        synth_parent = commit.alter(
          parents=[synth_parent.hsh] if synth_parent is not INVALID else [],
          tree=dir_tree,
          footers=collections.OrderedDict(footers),
        )

      if synth_parent is not INVALID:
        subtree_repo_push[subtree_repo[ref.ref]] = synth_parent

  t = Pusher(path, subtree_repo, subtree_repo_push)
  t.start()

  return success, synthed_count, t


def inner_loop(origin_repo, config):
  """Returns (success, {path: #commits_synthesized})."""

  origin_repo.fetch()
  config.evaluate()

  threads = []
  success = True
  processed = {}
  for path in config['enabled_paths']:
    LOGGER.info('processing path %s', path)
    try:
      path_success, num_synthed, t = process_path(path, origin_repo, config)
      threads.append(t)
      success = path_success and success
      processed[path] = num_synthed
    except Exception:  # pragma: no cover
      LOGGER.exception('Caught in inner_loop')
      success = False

  for t in threads:
    rslt = t.get_result()
    if not rslt:  # pragma: no cover
      success = False

  origin_repo.push_queued_fast_forwards(timeout=PUSH_TIMEOUT)

  return success, processed
