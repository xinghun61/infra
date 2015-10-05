#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Updates all SHA1s in Goopfile to point to current refs/heads/master.

Horribly slow, but simple.

Supposed to be followed by './env.py goop update' and manual examination of
all new wonderful packages we now depend on (to setup mirrors for them, etc).
See README.md.
"""

import os
import re
import subprocess
import sys
import urllib2


GO_DIR = os.path.dirname(os.path.abspath(__file__))


# Packages that should be checked out via some non-standard ref. Notable
# examples are packages distributed via gopkg.in hackery.
EXCEPTIONS = {
  'gopkg.in/fsnotify.v1': 'refs/tags/v1.2.0',
  'gopkg.in/yaml.v2': 'refs/heads/v2',
}


def parse_goop_line(line):
  """Line of Goop file -> (package name, ref, mirror repo or None)."""
  chunks = [c.strip() for c in line.split()]
  mirror = None
  if len(chunks) == 2:
    pkg, ref = chunks
  else:
    assert len(chunks) == 3, chunks
    pkg, ref, mirror = chunks
    assert mirror.startswith('!'), mirror
    mirror = mirror[1:]
  assert ref.startswith('#'), ref
  ref = ref[1:]
  return pkg, ref, mirror


def resolve_meta_import(pkg):
  """Package name -> what repo to fetch it from.

  Knows how to resolve <meta ...> redirects. See
  https://golang.org/cmd/go/#hdr-Remote_import_paths
  """
  # http://stackoverflow.com/a/1732454
  response = urllib2.urlopen('https://%s?go-get=1' % pkg).read()
  go_import = re.search(r'<meta name="go-import" content="(.+?)">', response)
  pkg_name, repo_type, repo_url = go_import.group(1).split()
  assert pkg_name == pkg, (pkg_name, pkg)
  assert repo_type == 'git', repo_type
  return repo_url


def get_latest_sha1(repo, ref=None):
  """Git repo URL -> SHA1 of go1 tag/ref or master ref."""
  if ref:
    refs = [ref]
  else:
    refs = ['refs/heads/master', 'refs/heads/go1', 'refs/tags/go1']
  out = subprocess.check_output(['git', 'ls-remote', repo] + refs)
  sha1s = {}
  for l in out.strip().splitlines():
    sha1, r = [s.strip() for s in l.split()]
    sha1s[r] = sha1
  if ref:
    return sha1s[ref]
  if 'refs/heads/go1' in sha1s:
    return sha1s['refs/heads/go1']
  if 'refs/tags/go1' in sha1s:
    return sha1s['refs/tags/go1']
  return sha1s['refs/heads/master']


def main():
  with open(os.path.join(GO_DIR, 'Goopfile'), 'rt') as f:
    goop = f.read()
  filtered = []
  for line in goop.splitlines():
    pkg, ref, mirror = parse_goop_line(line)
    latest = get_latest_sha1(
        repo=mirror or resolve_meta_import(pkg),
        ref=EXCEPTIONS.get(pkg))
    if ref == latest:
      print '%s is up-to-date' % pkg
    else:
      print '%s %s -> %s' % (pkg, ref, latest)
    if mirror:
      filtered.append('%s #%s !%s' % (pkg, latest, mirror))
    else:
      filtered.append('%s #%s' % (pkg, latest))
  new_goop = '\n'.join(filtered) + '\n'
  if new_goop.strip() == goop.strip():
    print 'No changes.'
    return 0
  with open(os.path.join(GO_DIR, 'Goopfile'), 'wt') as f:
    f.write(new_goop)
  return 0


if __name__ == '__main__':
  sys.exit(main())
