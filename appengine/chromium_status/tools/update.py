#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import sys
import argparse

ROOT = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
GAEPY = os.path.join(ROOT, 'gae.py')

INSTANCES = [
  'c-status',
  'chromium-status-hr',
  'chromiumos-status-hr',
  'dart-status',
  'infra-status',
  'naclports-status-hrd',
  'nativeclient-status-hrd',
  'v8-roll',
  'v8-status',
  'webrtc-status',
]


class MultipleChoiceAction(argparse.Action):

  def __call__(self, parser, namespace, values, option_string=None):
    if values:
      for value in values:
        if value not in INSTANCES:
          raise argparse.ArgumentError(
              self, 'Invalid choice %s (choose from %s)' % (value, INSTANCES))
      setattr(namespace, self.dest, values)
    else:
      setattr(namespace, self.dest, INSTANCES)


def main():
  p = argparse.ArgumentParser(
      description='Automatically update all instances of chromium_status.')
  p.add_argument(
      '-x', '--switch', action='store_true',
      help='Also switch to serving the new version')
  p.add_argument(
      'projects', nargs='*', action=MultipleChoiceAction,
      help='One or more projects to update (default: all)')
  args = p.parse_args()
  print('The following instances will be affected:')
  for instance in args.projects:
    print('  %s' % instance)

  s = ['-x'] if args.switch else []
  for instance in args.projects:
    print('\nDoing %s' % instance)
    subprocess.check_call(
        [sys.executable, GAEPY, 'upload', '-f'] + s + [ROOT, '-A', instance])


if __name__ == '__main__':
  sys.exit(main())
