# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import collections
import json
import logging
import re
import requests
import sys
import urlparse

from infra.libs import git2
from infra.libs import logs
from infra.libs.service_utils import outer_loop


# Git revision re.
GIT_HASH = re.compile(r'^[0-9a-f]{40}$')

# Return value of parse_args.
Options = collections.namedtuple('Options', 'specs loop_opts json_output')


def parse_args(args):  # pragma: no cover
  parser = argparse.ArgumentParser('python -m %s' % __package__)
  parser.add_argument('--dry_run', action='store_true',
                      help='Do not actually push anything.')
  parser.add_argument('--repo_dir', metavar='DIR', default='tag_pusher_repos',
                      help=('The directory to use for git clones '
                            '(default: %(default)s)'))
  parser.add_argument('--spec_json', metavar='SPEC', required=True,
                      help=('JSON file with configuration: '
                            '{<repo_url>: [{"refs" : [<ref>], "url": <url>}]}'))
  parser.add_argument('--json_output', metavar='PATH',
                      help='Path to write JSON with results of the run to')
  logs.add_argparse_options(parser)
  outer_loop.add_argparse_options(parser)

  opts = parser.parse_args(args)

  logs.process_argparse_options(opts)
  loop_opts = outer_loop.process_argparse_options(opts)

  # Read and validate the spec JSON.
  with open(opts.spec_json, 'r') as f:
    spec = json.load(f)
  if not isinstance(spec, dict):
    parser.error('Expecting dict as a spec')
  for repo_url, push_list in spec.iteritems():
    # Repo URL.
    parsed = urlparse.urlparse(repo_url)
    if parsed.scheme not in ('https', 'git', 'file'):
      parser.error('Repo URL must use https, git or file protocol.')
    if not parsed.path.strip('/'):
      parser.error('Repo URL is missing a path?')
    # Ref and URL to fetch.
    for d in push_list:
      refs = d.get('refs') or []
      url_to_read = d.get('url')
      for ref in refs:
        if not ref or not ref.startswith('refs/'):
          parser.error('Ref to push should start with refs/')
      if not url_to_read or not url_to_read.startswith('https://'):
        parser.error('URL to read SHA1 from should use https')

  # git2.Repo -> [([ref_to_push], url_to_read)].
  spec_by_repo = {}
  for url, push_list in spec.iteritems():
    repo = git2.Repo(url)
    repo.dry_run = opts.dry_run
    repo.repos_dir = opts.repo_dir
    spec_by_repo[repo] = [(d['refs'], d['url']) for d in push_list]

  return Options(spec_by_repo, loop_opts, opts.json_output)


def process_repo(repo, push_list):  # pragma: no cover
  ok = True
  try:
    repo.reify()
    repo.run('fetch', stdout=sys.stdout, stderr=sys.stderr)
    to_push = {}
    for refs, url_to_read in push_list:
      # Grab SHA1 from URL and validate it looks OK.
      response = requests.get(url_to_read)
      if response.status_code != 200:
        logging.error(
            'Failed to fetch %s: %s', url_to_read, response.text)
        ok = False
        continue
      sha1 = response.text.strip().lower()
      if not GIT_HASH.match(sha1):
        logging.error(
            'Body of %s doesn\'t look like valid git hash: %s',
            url_to_read, sha1)
        ok = False
        continue
      # Update the ref if required.
      commit = repo.get_commit(sha1)
      for ref in refs:
        if repo[ref].commit == commit:
          logging.info('%s is already at %s', ref, sha1)
        else:
          to_push[repo[ref]] = commit
    # Push new refs.
    repo.fast_forward_push(to_push)
    return ok, to_push
  except Exception:
    logging.exception('Error while processing %s', repo.url)
    return False, {}


def main(args):  # pragma: no cover
  opts = parse_args(args)

  all_pushes = []
  def outer_loop_iteration():
    success = True
    for repo, push_list in opts.specs.iteritems():
      ok, pushed_refs = process_repo(repo, push_list)
      success = success and ok
      all_pushes.extend([
        {
          'repo': repo.url,
          'ref': ref.ref,
          'commit': commit.hsh,
        } for ref, commit in pushed_refs.iteritems()
      ])
    return success

  loop_results = outer_loop.loop(
      task=outer_loop_iteration,
      sleep_timeout=lambda: 10,
      **opts.loop_opts)

  if opts.json_output:
    # (repo_url, ref) -> last pushed hash.
    last_pushes = {(p['repo'], p['ref']): p['commit'] for p in all_pushes}
    with open(opts.json_output, 'w') as f:
      json.dump({
        'all_pushes': all_pushes,
        'last_pushes': [
          {
            'repo': repo,
            'ref': ref,
            'commit': commit,
          } for (repo, ref), commit in last_pushes.iteritems()
        ]
      }, f)

  return 0 if loop_results.success else 1


if __name__ == '__main__':  # pragma: no cover
  sys.exit(main(sys.argv[1:]))
