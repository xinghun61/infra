# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool to check if the luci-milo.cfg matches buildbot

Example invocation:
./run.py infra.tools.luci_check <arguments>
"""

# This file is untested, keep as little code as possible in there.

import sys

from infra.tools.luci_check import luci_check
from infra_libs import app


class LuciCheck(app.BaseApplication):
  DESCRIPTION = sys.modules['__main__'].__doc__
  PROG_NAME = 'luci_check'

  def add_argparse_options(self, parser):
    super(LuciCheck, self).add_argparse_options(parser)
    parser.add_argument(
      '-c', '--console',
      default='https://chromium.googlesource.com/chromium/src/+/infra/'+
              'config/luci-milo.cfg')

  def main(self, opts):
    sys.exit(luci_check.Checker(opts.console).check())


if __name__ == '__main__':
  LuciCheck().run()
