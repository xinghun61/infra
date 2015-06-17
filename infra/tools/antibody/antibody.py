# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Testable functions for Antibody."""

import logging
import os
import sqlite3

from infra.tools.antibody import code_review_parse

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
RIETVELD_PARSE_DB = os.path.join(THIS_DIR, 'rietveld_parse.db')

# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument('--rietveld-url', '-ru', required=True,
                      help="url of rietveld code review to determine whether"
                           "the issue has been lgtm'ed or tbr'ed")
  parser.add_argument('--filename', '-f', default=RIETVELD_PARSE_DB,
                      help='file in which rietveld information will be kept')
                      

def setup_rietveld_db(rietveld_url, db_file):
  con = sqlite3.connect(db_file)
  with con:
    cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS rietveld (issue_num, ' + 
                'lgtm, tbr, request_timestamp, rietveld_url PRIMARY KEY)')
    code_review_parse.add_rietveld_data_to_db(rietveld_url, db_file)
