# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""<General description of List_running_masters here.>

[TBD] Example invocation:
./run.py infra.tools.list_running_masters <arguments>
"""
# This file is untested, keep as little code as possible in there.

import json
import logging
import sys

from infra.tools.list_running_masters import list_running_masters
from infra_libs import app


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)


class List_running_masters(app.BaseApplication):
  DESCRIPTION = sys.modules['__main__'].__doc__
  PROG_NAME = 'list_running_masters'

  def add_argparse_options(self, parser):
    super(List_running_masters, self).add_argparse_options(parser)
    parser.add_argument('-j', '--json', action='store_true',
        help='Emit JSON output instead of text.')

  def main(self, opts):
    running_masters = list_running_masters.get_running_masters()
    if not opts.json:
      print 'Found %d running master(s).' % (len(running_masters),)
      for master_name in sorted(running_masters.iterkeys()):
        pids = sorted(running_masters[master_name])
        print '%s: %s\n' % (master_name, ' '.join(str(x) for x in pids))
    else:
      json.dump(running_masters, sys.stdout, sort_keys=True, indent=2)
      sys.stdout.write('\n')


if __name__ == '__main__':
  List_running_masters().run()
