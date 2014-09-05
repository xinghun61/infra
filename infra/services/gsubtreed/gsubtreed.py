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
    'subtree_synthesized_prefix': lambda self, val: str(val),
    'subtree_processed_prefix': lambda self, val: str(val),

    'base_url': lambda self, val: str(val) if val else self.repo.url,
    'enabled_refglobs': lambda self, val: map(str, list(val)),
    # normpath to avoid trailing/double-slash errors.
    'enabled_paths': lambda self, val: map(posixpath.normpath, map(str, val)),
  }
  DEFAULTS = {
    'interval': 5.0,

    # e.g. while processing the subtree 'b/foo' on refs/heads/master
    #   refs/heads/master                              <- real commits
    #   refs/subtree-processed/b/foo/-/heads/master    <- ancestor tag of master
    #   refs/subtree-synthesized/b/foo/-/heads/master  <- ref with synth commits
    # For the sake of implementation simplicity, this daemon assumes the
    # googlesource.com guarantee of transactional multi-ref pushes within a
    # single repo.
    'subtree_processed_prefix': 'refs/subtree-processed',
    'subtree_synthesized_prefix': 'refs/subtree-synthesized',

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
  def __init__(self, name, dest_repo, pushspec):
    super(Pusher, self).__init__()
    self._name = name
    self._repo = dest_repo
    self._pushspec = pushspec

    self._success = False
    self._output = None

  def run(self):
    try:
      self._output = self._repo.fast_forward_push(
          self._pushspec, include_err=True, timeout=PUSH_TIMEOUT)
      self._success = True
    except CalledProcessError as cpe:  # pragma: no cover
      self._output = str(cpe)

  def get_result(self):
    self.join()
    log = logging.info if self._success else logging.error
    prefix = 'Completed' if self._success else 'FAILED'
    log("%s push for %r", prefix, self._name)
    if self._output:
      log(self._output)  # pragma: no cover
    return self._success


def process_path(path, origin_repo, config):
  def join(prefix, ref):
    assert ref.ref.startswith('refs/')
    ref = '/'.join((prefix, path)) + '/-/' + ref.ref[len('refs/'):]
    return origin_repo[ref]

  origin_push = {}

  base_url = config['base_url']
  mirror_url = '[FILE-URL]' if base_url.startswith('file:') else origin_repo.url

  subtree_repo = repo.Repo(posixpath.join(base_url, path))
  subtree_repo.repos_dir = origin_repo.repos_dir
  subtree_repo.reify(share_from=origin_repo)
  subtree_repo.run('fetch', stdout=sys.stdout, stderr=sys.stderr)
  subtree_repo_push = {}

  synthed_count = 0

  for glob in config['enabled_refglobs']:
    for ref in origin_repo.refglob(glob):
      LOGGER.info('processing ref %s', ref)
      processed = join(config['subtree_processed_prefix'], ref)
      synthed = join(config['subtree_synthesized_prefix'], ref)

      synth_parent = synthed.commit
      LOGGER.info('starting with tree %r', synthed.commit.data.tree)

      for commit in processed.to(ref, path):
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
        origin_push[synthed] = synth_parent
        subtree_repo_push[subtree_repo[ref.ref]] = synth_parent
      origin_push[processed] = ref.commit

  success = True
  # TODO(iannucci): Return the pushspecs from this method, and then thread
  # the dispatches to subtree_repo. Additionally, can batch the origin_repo
  # pushes (and push them serially in batches as the subtree_repo pushes
  # complete).

  # because the hashes are deterministic based on the real history, the pushes
  # can happen completely independently. If we miss one, we'll catch it on the
  # next pass.
  try:
    origin_repo.queue_fast_forward(origin_push)
  except Exception:  # pragma: no cover
    LOGGER.exception('Caught exception while queuing origin in process_path')
    success = False

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
