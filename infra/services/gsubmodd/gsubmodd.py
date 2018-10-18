# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import itertools
import logging
import re

from infra.libs.deps2submodules import deps2submodules
from infra.libs.git2 import CalledProcessError
from infra.libs.git2 import INVALID
from infra.libs.git2 import repo

SHA1_RE = re.compile(r'[0-9a-fA-F]{40}')  # TODO: move this to git2.data

PUSH_TIMEOUT = 18 * 60
MIRRORED_COMMIT = 'Cr-Mirrored-Commit'

LOGGER = logging.getLogger(__name__)

# We only care about the master branch.
REF_NAME = 'refs/heads/master'

# The last commit in chromium/src that was copied from Subversion.
# Only commits after this can be relied upon to have a suitable DEPS
# file, so we start here.  (In other repos we can simply start at the
# beginning of history.)
#
# TODO(crbug/895967): move this to builder config, once the ability
# to specify on the command line has been deployed.
_CHROMIUM_SRC_EPOCH='3c70abf6069f043037e9f932f62e0cb45e6592fe'


# TODO: this was cloned from sync_submodules/api.py.  Refactor for sharing?
def _Humanish(url):
  if url.endswith('.git'):
    url = url[:-4]
  slash = url.rfind('/')
  if slash != -1:  # pragma: no cover
    url = url[slash + 1:]
  return url


def reify_submodules(origin_repo, target, dry_run=False,
                     limit=None, extra_submodules=None, epoch=None):
  origin_repo.fetch()

  shadow = repo.Repo(target)
  shadow.dry_run = dry_run
  shadow.repos_dir = origin_repo.repos_dir
  shadow.reify(share_from=origin_repo)

  synth_parent = shadow["refs/heads/master"].commit
  if synth_parent is INVALID:
    # If the shadow repo doesn't have any commits yet (we're just
    # starting up for the first time), start at the beginning of history
    # at the origin repo, either the absolute beginning, or the "epoch"
    # at which we are configured to start.
    if epoch:
      processed = origin_repo.get_commit(epoch)
      if processed is INVALID:
        LOGGER.error("Requested epoch commit %s does not exist", epoch)
        return False
    else:
      # For now, preserve the former behavior when this new "epoch" optional
      # argument is missing.  But once this new capability is deployed, the
      # default behavior here should simply be to always start at the absolute
      # beginning: i.e., there's no reason to default to the _CHROMIUM_SRC_EPOCH
      # once that value can be explicitly passed in to us from the config.
      #
      # Note that looking up _CHROMIUM_SRC_EPOCH on repos other than
      # chromium/src produces INVALID, and that's fine (it means we'll
      # start at the beginning of history).
      processed = origin_repo.get_commit(_CHROMIUM_SRC_EPOCH)
  else:
    footers = synth_parent.data.footers
    if MIRRORED_COMMIT not in footers:
      LOGGER.error('No footers for synthesized commit %r', synth_parent.hsh)
      return False
    processed_commit_hash = footers[MIRRORED_COMMIT][0]
    processed = origin_repo.get_commit(processed_commit_hash)
    if processed is INVALID:
      LOGGER.error('Mirrored commit %s (from synth. commit %r) does not exist',
                   processed_commit_hash, synth_parent.hsh)
      return False
    LOGGER.info('starting with tree %r', synth_parent.data.tree)

  count = 0
  known_hash = ''
  submods = None
  path_prefix = '%s/' % _Humanish(origin_repo.url)
  resolver = deps2submodules.GitRefResolver(shadow)
  commits = origin_repo[processed.hsh].to(origin_repo[REF_NAME],
                                          '', first_parent=True)
  for commit in itertools.islice(commits, limit):
    LOGGER.info("at commit %s" % commit.hsh)
    original_tree = commit.data.to_dict()['tree']

    deps_info = origin_repo.run('ls-tree', commit.hsh, '--', 'DEPS').split()
    if len(deps_info):
      # ls-tree output looks something like this:
      #     100644 blob 726d435df65288b740ea55d38a5070c9870b8172        DEPS
      deps_hash = deps_info[2]
      assert SHA1_RE.match(deps_hash)
      if deps_hash == known_hash:
        # DEPS file has not changed in this commit: no need to repeat
        # the parsing/processing of it.
        #
        # TODO: When we add support for recurse-deps, either remove or refine
        # this optimization.  (Even if top-level DEPS hasn't changed, the DEPS
        # of a submodule might have.)
        pass
      else:
        # new version of DEPS file
        deps_object_path = '%s:DEPS' % commit.hsh
        deps_content = origin_repo.run('cat-file', 'blob', deps_object_path)
        if known_hash:
          LOGGER.debug('commit %s has modified DEPS file' % commit.hsh)
          submods = submods.withUpdatedDeps(deps_content)
        else:
          submods = deps2submodules.Deps2Submodules(deps_content,
              resolver, path_prefix, extra_submodules)
        submods.Evaluate()
        known_hash = deps_hash

      try:
        new_tree = submods.UpdateSubmodules(shadow, commit.hsh)
      except Exception as e:  # pragma: no cover
        # TODO: build a wrapping exception the proper way
        LOGGER.error("exception happened on %s: %s" % (commit.hsh, str(e)))
        raise

    else:
      # DEPS file does not even exist.  This should only happen in the
      # very earliest commits of repos (and never in chromium/src,
      # because we went to the trouble of finding epoch).
      LOGGER.warn('commit %s has no DEPS file' % commit.hsh)
      new_tree = original_tree


    footers = [(MIRRORED_COMMIT, [commit.hsh])]
    data = commit.data.alter(
        parents=[synth_parent.hsh] if synth_parent is not INVALID else [],
        tree=new_tree,
        footers=collections.OrderedDict(footers)
    )
    synth_parent = shadow.get_commit(shadow.intern(data, 'commit'))
    count += 1

  if count:
    output = shadow.fast_forward_push({shadow[REF_NAME]:synth_parent},
                                      include_err=True, timeout=PUSH_TIMEOUT)
    if output:  # pragma: no cover
      LOGGER.info(output)

  return True
