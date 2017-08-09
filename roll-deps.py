#!/usr/bin/env python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Automatically rolls the DEPS entries for specified repositories."""

import argparse
import ast
import logging
import os
import subprocess
import sys


INFRA_PATH = os.path.dirname(os.path.abspath(__file__))
DEPS_PATH = os.path.join(INFRA_PATH, 'DEPS')


# List of "deps" paths to automatically roll.
_DEFAULT_ROLL = (
  'infra/go/src/go.chromium.org/luci',
  'infra/go/src/go.chromium.org/gae',
)


def _do_roll(gclient_root, path, rev):
  # Localize the path.
  if os.sep != '/':
    path = path.replace('/', os.sep)
  path = os.path.join(gclient_root, path)

  subprocess.check_call(['git', '-C', path, 'fetch', 'origin'])
  stdout = subprocess.check_output(['git', '-C', path, 'rev-parse',
                                    'origin/master']).strip()
  if rev == stdout:
    return rev, ()

  # Get the change log.
  changelog = subprocess.check_output(['git', '-C', path, 'log', '--oneline',
                                       '%s..%s' % (rev, stdout)])
  return stdout.strip(), changelog


def _find_gclient_root():
  cur = INFRA_PATH
  while True:
    candidate = os.path.join(cur, '.gclient')
    if os.path.isfile(candidate):
      return cur
    cur, tail = os.path.split(cur)
    if tail == '':
      raise Exception('Could not find .gclient file.')


class Editor(object):
  """Minimal implementation that replaces values by line."""
  def __init__(self, content):
    self._lines = content.split('\n')

  def replace_next(self, line, old, new):
    line -= 1 # AST line count starts at 1
    for l in xrange(line, len(self._lines)):
      cur = self._lines[l]
      idx = cur.find(old)
      if idx < 0:
        continue
      self._lines[l] = cur[:idx] + new + cur[idx+len(old):]
      return
    raise ValueError('Could not find line containing [%s]' % (old,))

  def __str__(self):
    return '\n'.join(self._lines)


def main(args):
  parser = argparse.ArgumentParser()
  parser.add_argument('path', nargs='*',
      help='The DEPS path to roll. If none are supplied, a set of default '
           'paths will be rolled.')
  opts = parser.parse_args(args)

  roll_whitelist = set(opts.path)
  if not roll_whitelist:
    roll_whitelist.update(_DEFAULT_ROLL)

  gclient_root = _find_gclient_root()

  with open(DEPS_PATH, 'r') as fd:
    content = fd.read()
  t = ast.parse(content)
  ed = Editor(content)

  # Find our "deps" dictionary in our AST.
  entry = None
  for entry in t.body:
    if not isinstance(entry, ast.Assign):
      continue
    if len(entry.targets) != 1:
      continue
    if entry.targets[0].id != 'deps':
      continue
    break
  else:
    raise ValueError('Could not find deps node')

  changelog = []
  if not isinstance(entry.value, ast.Dict):
    raise TypeError('deps not is not a dict')
  for i, k in enumerate(entry.value.keys):
    if not isinstance(k, ast.Str):
      continue
    if k.s not in roll_whitelist:
      continue
    v = entry.value.values[i]
    if not isinstance(v, ast.Str):
      logging.warning('Revision for [%s] is not a string.', k.s)
      continue

    parts = v.s.split('@', 1)
    if len(parts) != 2:
      logging.info('Could not process repo/revision for [%s]', v.s)
      continue
    _, rev = parts

    logging.info('Rolling [%s]...', k.s)
    newrev, changes = _do_roll(gclient_root, k.s, rev)
    if newrev == rev:
      logging.debug('[%s] is up to date.', k.s)
      continue

    logging.info('Rolling [%s]: [%s] => [%s]', k.s, rev, newrev)
    changelog.append((k.s, changes))
    ed.replace_next(v.lineno, rev, newrev)

  if len(changelog) > 0:
    with open(DEPS_PATH, 'w') as fd:
      fd.write(str(ed))

    for path, changes in changelog:
      sys.stdout.write('\n%s:\n%s' % (path, changes))

  return 0


if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  sys.exit(main(sys.argv[1:]))
