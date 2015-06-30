# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Testable functions for Antibody."""

import jinja2
import logging
import os

import infra.tools.antibody.cloudsql_connect as csql

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
ANTIBODY_UI = os.path.join(THIS_DIR, 'antibody_ui.html')
# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument('--cache-path', '-c', help="path to the rietveld cache")
  parser.add_argument('--git-checkout-path', '-g', required=True,
                      help="path to the git checkout")
  parser.add_argument('--sql-password-file', '-p', required=True,
                      help="password for cloud sql instance")
  parser.add_argument('--write-html', '-w', action='store_true',
                      help="generates the ui ")
  parser.add_argument('--run-antibody', '-a', action='store_true',
                      help="runs the pipeline from git checkout"
                           "to generation of ui")
  parser.add_argument('--parse-git-rietveld', '-r', action='store_true',
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
