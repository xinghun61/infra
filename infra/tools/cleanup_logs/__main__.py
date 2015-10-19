# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import fnmatch
import os
import sys
import time

import infra_libs

DIRECTORIES = {
  'linux2': [
    ('/tmp', '*.log.*'),
    ('/var/log/chrome-infra', '*.log.*'),
  ],
  'darwin': [
    ('/tmp', '*.log.*'),
    ('/Users/chrome-bot/Library/Logs/CoreSimulator', None),
    ('/var/log/chrome-infra', '*.log.*'),
  ],
  'win32': [
    ('C:\\chrome-infra-logs', '*.log.*'),
    ('E:\\chrome-infra-logs', '*.log.*'),
  ],
}

MAX_AGE_SECS = 2 * 24 * 60 * 60  # 2 days


class CleanupLogs(infra_libs.BaseApplication):
  DESCRIPTION = 'Deletes log files that haven\'t been modified for 2 days.'

  def add_argparse_options(self, parser):
    # Don't call the base class so we don't add logs or ts_mon.
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Just print the files that would otherwise be deleted.')

  def process_argparse_options(self, options):
    # Don't call the base class so we don't initialise logs or ts_mon.
    pass

  def main(self, opts):
    delete_before = time.time() - MAX_AGE_SECS

    for path, pattern in DIRECTORIES[sys.platform]:
      if not os.path.isdir(path):
        continue

      names = os.listdir(path)
      if pattern is not None:
        names = fnmatch.filter(names, pattern)
      print 'Found %d files in %s' % (len(names), path)

      for name in names:
        filepath = os.path.join(path, name)
        if os.path.getctime(filepath) < delete_before:
          print 'Deleting', filepath
          if not opts.dry_run:
            if os.path.isdir(filepath):
              infra_libs.rmtree(filepath)
            else:
              os.unlink(filepath)


if __name__ == '__main__':
  CleanupLogs().run()
