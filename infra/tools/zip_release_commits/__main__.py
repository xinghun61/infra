#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Hacky tool to update uber-ref containing all release tags.

Due to a variety of amusing reasons, this is expected to significantly improve
the performance of the chromium/src git repo, due to the way that refs/tags is
used.
"""

import argparse
import os
import sys

from infra.libs import logs

from infra.libs.git2 import Repo, INVALID, CalledProcessError


def main(argv):
  p = argparse.ArgumentParser()
  p.add_argument(
    '--repo-dir', metavar='DIR', default='zip_release_commits_repos',
    help='The directory to use for git clones (default: %(default)s).')
  logs.add_argparse_options(p)
  opts = p.parse_args(argv)
  logs.process_argparse_options(opts)

  # Get all refs
  r = Repo('https://chromium.googlesource.com/chromium/src')
  r.repos_dir = os.path.abspath(opts.repo_dir)
  r.reify()
  r.fetch()

  all_releases = r['refs/heads/ignore/foo']

  tags = r.run(
    'for-each-ref', '--sort=committerdate', '--format=%(objectname) %(refname)',
    'refs/tags'
  ).splitlines()

  already_have = set()
  try:
    already_have = r.run('rev-list', '--first-parent', '--parents',
                         all_releases.ref).splitlines()
    # Last commit in chain is the null commit
    already_have = set(l.split()[-1] for l in already_have[:-1])
  except CalledProcessError:
    pass

  for hsh_tag in tags:
    hsh, tag = hsh_tag.split()
    if hsh in already_have:
      print 'skipping', tag
      continue

    print 'processing', tag
    c = r.get_commit(hsh)
    if all_releases.commit is INVALID:
      cu = c.data.committer
      cu = cu.alter(timestamp=cu.timestamp.alter(secs=cu.timestamp.secs-1))
      au = c.data.author
      au = au.alter(timestamp=au.timestamp.alter(secs=au.timestamp.secs-1))

      all_releases.update_to(c.alter(
        author=au,
        committer=cu,
        parents=(),
        tree=None,
      ))

    parents = [all_releases.commit.hsh, c.hsh]
    all_releases.update_to(c.alter(
      author=c.data.committer,
      message_lines=[tag],
      parents=parents,
      tree=None,
    ))

  print all_releases.commit
  r.run('push', 'origin', '%s:%s' % (all_releases.commit.hsh, all_releases.ref))


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
