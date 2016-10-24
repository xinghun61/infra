# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import logging
import os
import sys

_SCRIPT_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir,
                           os.path.pardir)
sys.path.insert(1, _SCRIPT_DIR)

import script_util
script_util.SetUpSystemPaths()

from crash.findit_for_chromecrash import Culprit
from crash_queries.delta_test import delta_util


# TODO(katesonia): Replace the current testing function with real find culprit
# function.
def GetCulprits(crashes):
  culprits = {}
  for crash in crashes:
    culprit = Culprit('proj', 'comp', [], ['rev1', 'rev2'])
    culprits[crash['id']] = culprit

  return culprits


def RunPredator():
  """Runs delta testing between 2 different Findit versions."""
  argparser = argparse.ArgumentParser(
      description='Run azalea on a batch of crashes.')
  argparser.add_argument('result_path', help='Path to store results')
  argparser.add_argument(
      '--verbose',
      '-v',
      action='store_true',
      default=False,
      help='Print findit results.')
  argparser.add_argument(
      '--client',
      '-c',
      default='fracas',
      help=('Possible values are: fracas, cracas, clusterfuzz. Right now, only '
            'fracas is supported.'))
  args = argparser.parse_args()

  crashes = json.loads(raw_input())
  culprits = GetCulprits(crashes)

  delta_util.FlushResult(culprits, args.result_path)


if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  RunPredator()
