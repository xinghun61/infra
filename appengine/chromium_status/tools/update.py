#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
APPCFG = os.path.join(ROOT, '..', 'google_appengine', 'appcfg.py')

INSTANCES = [
  'chromeos-status-hrd',
  'chromium-status-hr',
  'chromiumos-status-hr',
  'dart-status',
  'fletch-status',
  'gyp-status-hrd',
  'naclports-status-hrd',
  'nativeclient-status-hrd',
  'o3d-status-hr',
  'v8-roll',
  'v8-status',
  'webrtc-status',
]

def main():
  if not sys.argv[1:]:
    print('Usage: update.py <appcfg.py command> -V <version to use>')
    print('Examples:')
    print('  update.py update -V r94532')
    print('  update.py set_default_version -V r94532')
    print('')
    print('The following instances will be affected:')
    for instance in INSTANCES:
      print('  %s' % instance)
    print('')
    return 1

  command = sys.argv[1:]
  for instance in INSTANCES:
    print('\nDoing %s' % instance)
    subprocess.check_call(
        [sys.executable, APPCFG] + command + [ROOT, '-A', instance])
  return 0


if __name__ == '__main__':
  sys.exit(main())
