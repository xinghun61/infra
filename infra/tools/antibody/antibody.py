# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Testable functions for Antibody."""

import logging
import os
import sys

try:
 sys.path.append('/usr/lib/python2.7/dist-packages/')
 import MySQLdb
except ImportError:
 pass
finally:
 sys.path.remove('/usr/lib/python2.7/dist-packages/')

import infra.tools.antibody.cloudsql_connect as csql
from infra.tools.antibody import code_review_parse
from infra.tools.antibody import git_commit_parser


# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument('--rietveld-url', '-r', 
                      help="url of rietveld code review to determine whether"
                           "the issue has been lgtm'ed or tbr'ed")
  parser.add_argument('--sql-password-file', '-p', required=True,
                      help="password for cloud sql instance")


def setup_antibody_db(cc):  # pragma: no cover
    csql.create_tables(cc)