# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Antibody is meant to audit reviews for the Chromium project.

Example invocation: [TBD]
  ./run.py infra.tools.antibody <arguments>
"""

# This file is untested, keep as little code as possible in there.

import argparse
import logging
import sys

from infra.tools.antibody import antibody
import infra_libs.logs


# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


def main(argv):
  parser = argparse.ArgumentParser(
    prog="antibody",
    description=sys.modules['__main__'].__doc__)
  antibody.add_argparse_options(parser)
  infra_libs.logs.add_argparse_options(parser)
  args = parser.parse_args(argv)

  infra_libs.logs.process_argparse_options(args)

  # Do more processing here
  LOGGER.info('Antibody starting')
  
  antibody.setup_rietveld_db(args.rietveld_url, args.filename)

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
