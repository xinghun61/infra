# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Generate a new tool in infra/tools."""

import argparse
import sys

from infra.tools.new_tool import new_tool


def main(argv):
  parser = argparse.ArgumentParser(
    prog='new_tool',
    description=sys.modules['__main__'].__doc__)
  new_tool.add_argparse_options(parser)
  args = parser.parse_args(argv)

  return new_tool.generate_tool_files(args.name[0], args.base_dir)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
