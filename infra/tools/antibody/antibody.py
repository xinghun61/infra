# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Testable functions for Antibody."""

import logging
import os
import sqlite3
import sys

from infra.tools.antibody import code_review_parse
from infra.tools.antibody import git_commit_parser

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ANTIBODY_DB = os.path.join(THIS_DIR, 'antibody.db')

# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument('--rietveld-url', '-r', 
                      help="url of rietveld code review to determine whether"
                           "the issue has been lgtm'ed or tbr'ed")
  parser.add_argument('--filename', '-f', default=ANTIBODY_DB,
                      help='file in which rietveld information will be kept')
                      

def setup_antibody_db(db_file=ANTIBODY_DB):  # pragma: no cover
  with sqlite3.connect(db_file) as con:
    cur = con.cursor()
    git_commit_parser.create_table(cur)
    code_review_parse.create_table(cur)
