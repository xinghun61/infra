# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool to check if the luci-milo.cfg matches buildbot

Example invocation:
./run.py infra.tools.luci_check <arguments>
"""

import json
import os
import sys

from infra.tools.luci_check import luci_check
from infra_libs import app


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(THIS_DIR, 'config')


class LuciCheck(app.BaseApplication):
  DESCRIPTION = sys.modules['__main__'].__doc__
  PROG_NAME = 'luci_check'

  @staticmethod
  def get_masters():
    with open(os.path.join(CONFIG_DIR, 'masters.json')) as f:
      return json.load(f)

  def add_argparse_options(self, parser):
    super(LuciCheck, self).add_argparse_options(parser)
    parser.add_argument(
      '-c', '--console',
      default='https://chromium.googlesource.com/chromium/src/+/master/infra/' +
              'config/global/luci-milo.cfg')
    parser.add_argument(
      '-m', '--master', action='append', help="consider these masters",
      dest='masters')

  def main(self, opts):
    if not opts.master:
      opts.master = self.get_masters()
    sys.exit(luci_check.Checker(opts.console, opts.masters).check())


if __name__ == '__main__':
  LuciCheck().run()
