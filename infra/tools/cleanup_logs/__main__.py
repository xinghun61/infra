# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import fnmatch
import os
import sys
import time

import infra_libs

DEFAULT_MAX_AGE_SECS = 2 * 24 * 60 * 60  # 2 days

# platform -> (directory, pattern, max age in secs)
DIRECTORIES = {
  'linux2': [
    ('/tmp', '*.log.*', None),
    ('/var/log/chrome-infra', '*.log.*', None),
    ('/home/chrome-bot/.config/chromium/Crash Reports', None, 10 * 3600),
  ],
  'darwin': [
    ('/tmp', '*.log.*', None),
    ('/Users/chrome-bot/Library/Logs/CoreSimulator', None, None),
    ('/var/log/chrome-infra', '*.log.*', None),
  ],
  'win32': [
    ('C:\\chrome-infra-logs', '*.log.*', None),
    ('E:\\chrome-infra-logs', '*.log.*', None),
    ('C:\\Users\\chrome-bot\\AppData\\Local\\Temp', None, 10 * 3600),
  ],
}


class CleanupLogs(infra_libs.BaseApplication):
  DESCRIPTION = 'Deletes log files that haven\'t been modified for 2 days.'

  def add_argparse_options(self, parser):
    # Don't call the base class so we don't add logs or ts_mon.
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Just print the files that would otherwise be deleted.')

  def process_argparse_options(self, options):
    # TODO(pgervais,http://crbug.com/564737): having metrics would be useful
    # Don't call the base class so we don't initialise logs or ts_mon.
    pass

  def main(self, opts):
    for path, pattern, max_age_secs in DIRECTORIES[sys.platform]:
      max_age_secs = max_age_secs or DEFAULT_MAX_AGE_SECS
      delete_before = time.time() - max_age_secs

      if not os.path.isdir(path):
        continue

      # TODO(pgervais,http://crbug.com/564743): make this recursive
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
