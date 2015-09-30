# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities to deal with metrics.

Extracting all metrics in a set of Python files:
./run.py infra.tools.metric_tool extract
"""
# This file is untested, keep as little code as possible in there.

import logging
import sys

from infra.tools.metric_tool import metric_tool
import infra_libs


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)


class Metric_tool(infra_libs.BaseApplication):
  DESCRIPTION = sys.modules['__main__'].__doc__
  PROG_NAME = 'metric_tool'

  def add_argparse_options(self, parser):
    super(Metric_tool, self).add_argparse_options(parser)
    parser.add_argument('path', type=str,
                        help='Directory to recursively scan for Python files.')

  def main(self, opts):
    # Do more processing here
    metric_tool.main(opts.path)


if __name__ == '__main__':
  Metric_tool().run()
