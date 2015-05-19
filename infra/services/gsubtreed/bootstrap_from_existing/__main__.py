# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import collections
import argparse
import hashlib
import sys

from infra.libs.git2 import Repo
from infra_libs import logs

from infra.services.gsubtreed.gsubtreed import MIRRORED_COMMIT


CHROMIUM_URL = 'https://chromium.googlesource.com/chromium/src'


NOTE = collections.namedtuple('NOTE', 'url obj commit')


def find_svn_num_commit(repo, ref, commit):
  rev = int(commit.data.footers.get('git-svn-id')[0].split()[0].split('@')[-1])
  commits = repo.run('rev-list', ref, '--grep',
                     'svn://svn.chromium.org/chrome/trunk/src@%s' % rev)
  return repo.get_commit(commits.splitlines()[0])


def process_path(repo, subpath):
  sub_url = '/'.join([CHROMIUM_URL, subpath])
  remote_name = hashlib.sha1(sub_url).hexdigest()
  repo.run('config', 'remote.%s.url' % remote_name, sub_url)
  repo.run('config', 'remote.%s.fetch' % remote_name,
           '+refs/*:refs/remotes/%s/*' % remote_name)

  repo.run('fetch', remote_name)

  current_synth = repo['refs/remotes/%s/heads/master' % remote_name].commit
  matched_processed_commit = find_svn_num_commit(
    repo, 'refs/heads/master', current_synth)

  return [NOTE(sub_url, current_synth.hsh, matched_processed_commit.hsh)]


def main(argv):
  p = argparse.ArgumentParser()
  p.add_argument('--dry-run', action='store_true',
                 help='Make plan but do nothing.')
  p.add_argument('--reference', metavar='DIR',
                 help='Path to a repo to use for reference.')
  p.add_argument('--repo-dir', metavar='DIR', default='bootstrap_from_existing',
                 help=('The directory to use for git clones '
                       '(default: %(default)s)'))
  p.add_argument('subpath', nargs='*', help='subpaths to mirror from')
  logs.add_argparse_options(p)
  opts = p.parse_args(argv)
  logs.process_argparse_options(opts)

  # TODO(iannucci): make this work for other refs?

  repo = Repo(CHROMIUM_URL)
  repo.repos_dir = os.path.abspath(opts.repo_dir)
  repo.reify(share_from=opts.reference)
  repo.run('fetch')

  plan = []

  for path in opts.subpath:
    plan.extend(process_path(repo, path))

  print 'Plan of attack: '
  for task in plan:
    print '  Note ', '%r: %s mirrored from %s' % task
  print

  prompt = 'yes'.startswith(raw_input('Continue? [y/N] ').lower() or 'no')
  if opts.dry_run or not prompt:
    print 'Doing nothing'
    return 0

  for sub_url, obj, matched in plan:
    remote_name = hashlib.sha1(sub_url).hexdigest()
    notes_ref = 'refs/remotes/%s/notes/extra_footers' % remote_name
    repo.run('notes', '--ref', notes_ref, 'add',
             '-m', '%s: %s' % (MIRRORED_COMMIT, matched), obj)
    repo.run('push', remote_name, '%s:refs/notes/extra_footers' % (notes_ref,))

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
