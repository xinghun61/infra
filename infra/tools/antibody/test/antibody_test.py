# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool-specific testable functions for antibody."""

import argparse
import json
import os
import re
import sqlite3

import infra_libs
from testing_support import auto_stub
from infra.tools.antibody import code_review_parse
from infra.tools.antibody import antibody


class MyTest(auto_stub.TestCase):
  def test_arguments(self):
    parser = argparse.ArgumentParser()
    antibody.add_argparse_options(parser)
    args = parser.parse_args(['--rietveld-url', '1234'])
    self.assertEqual(args.rietveld_url, '1234')

    args = parser.parse_args(['-r', '5678'])
    self.assertEqual(args.rietveld_url, '5678')

    args = parser.parse_args(['-f', 'abc'])
    self.assertEqual(args.filename, 'abc')
