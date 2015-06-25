# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Testable functions for Antibody."""

import jinja2
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

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
ANTIBODY_UI = os.path.join(THIS_DIR, 'antibody_ui.html')
# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument('--rietveld-url', '-r', 
                      help="url of rietveld code review to determine whether"
                           "the issue has been lgtm'ed or tbr'ed")
  parser.add_argument('--sql-password-file', '-p', required=True,
                      help="password for cloud sql instance")
  parser.add_argument('--write-html', '-w', action='store_true',
                      help="generates the ui ")
  parser.add_argument('--run-antibody', '-a', action='store_true',
                      help="runs the pipeline from git checkout"
                           "to generation of ui")
  parser.add_argument('--parse-git-rietveld', '-g', action='store_true',
                      help="runs the pipeline from git checkout"
                           "to parsing of rietveld")


def setup_antibody_db(cc):  # pragma: no cover
  csql.create_tables(cc)


def generate_antibody_ui(suspicious_commits_data, gitiles_prefix, 
                         ui_filename=ANTIBODY_UI):
  templateLoader = jinja2.FileSystemLoader(os.path.join(THIS_DIR, 'templates'))
  templateEnv = jinja2.Environment(loader=templateLoader)
  template = templateEnv.get_template('antibody_ui.jinja')
  
  templateVars = {'title' : 'Potentially Suspicious Commits to Chromium',
                  'description' : 'List of commits with a TBR but no lgtm',
                  'page_header_text' : "Potentially Suspicious Commits",
                  'table_headers' : ['git_hash', 'rietveld_url', 
                                     'request_timestamp'],
                  'suspicious_commits' : suspicious_commits_data,
                  'gitiles_prefix' : gitiles_prefix,
                 }
  
  with open(ui_filename, 'wb') as f:
    f.write(template.render(templateVars))  