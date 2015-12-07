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


# These packages must not be moved due to breaking changes.
MUST_BE_PINNED = [
    "github.com/golang/protobuf",  # https://github.com/luci/luci-go/issues/7
]


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


def get_latest_refs(repo):
  """Git repo URL -> map {refs|tags => sha1}."""
  out = subprocess.check_output(['git', 'ls-remote', repo])
  sha1s = {}
  for l in out.strip().splitlines():
    sha1, r = [s.strip() for s in l.split()]
    sha1s[r] = sha1
  return sha1s


def pick_ref(pkg, refs):
  """Given a dict with repo refs, chooses the one to put in Goopfile.

  Uses default 'go get' rules, unless packages are known to use some custom
  scheme, e.g. packages imported via 'gopkg.in/*'.
  """
  # gopkg.in package with custom ref rules?
  gopkg_in = re.match(r'^gopkg\.in/.*\.v([0-9]+)$', pkg)
  if gopkg_in:
    requested_ver = int(gopkg_in.group(1))
    return pick_gopkgin_ref(refs, requested_ver)

  # Default 'go get' rules.
  for ref in ('refs/heads/go1', 'refs/tags/go1', 'refs/heads/master'):
    if ref in refs:
      return refs[ref]

  raise ValueError('Can\'t pick a ref for %s from %s' % (pkg, refs))


def pick_gopkgin_ref(refs, requested_ver):
  """Chooses a refs that best matches requested version.

  Implements gopkg.in rules as described at http://labix.org/gopkg.in.
  See "Version number" section.
  """
  # Make a map (version tuple => SHA1). Choose heads over tags.
  versions = {}
  for ref in sorted(refs, key=lambda r: r.startswith('refs/tags/')):
    name = ref[ref.rfind('/')+1:] # e.g. "v1.0.1"
    if name[0] == 'v':
      ver = tuple(map(int, name[1:].split('.')))
      if ver[0] == requested_ver and ver not in versions:
        versions[ver] = refs[ref]
  if not versions:
    raise ValueError('Can\'t find v%d in %s' % (requested_ver, refs))

  # Find best matching version.
  best = versions.keys()[0]
  for ver in versions:
    if is_newer_version(ver, best):
      best = ver
  return versions[best]


def is_newer_version(a, b):
  """Given two version tuples, returns True if version `a` is newer than `b`.

  Rules (examples):
    1.0.0 > 1.0
    1.1 > 1.0.0
    2 > 1.1
  """
  for i in xrange(max(len(a), len(b))):
    a_i = a[i] if i < len(a) else -1
    b_i = b[i] if i < len(b) else -1
    if a_i > b_i:
      return True
    if a_i < b_i:
      return False
  return False # equal


def main():
  with open(os.path.join(GO_DIR, 'Goopfile'), 'rt') as f:
    goop = f.read()
  filtered = []
  for line in goop.splitlines():
    pkg, ref, mirror = parse_goop_line(line)
    refs = get_latest_refs(mirror or resolve_meta_import(pkg))
    latest = pick_ref(pkg, refs)
    if ref == latest:
      print '%s is up-to-date' % pkg
    else:
      if pkg in MUST_BE_PINNED:
        print '%s has newer version we ignore (%s)' % (pkg, latest)
        latest = ref
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
