# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Testable functions for Antibody."""

import jinja2
import json
import logging
import os

import infra.tools.antibody.cloudsql_connect as csql

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
ANTIBODY_UI_MAIN_NAME = 'index.html';
TBR_BY_USER_NAME = 'tbr_by_user.html';

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
  parser.add_argument('--output-dir-path', '-d', default=THIS_DIR,
                      help="path to directory in which the ui will be"
                           "generated")
  


def setup_antibody_db(cc):  # pragma: no cover
  csql.create_tables(cc)


def generate_antibody_ui(suspicious_commits_data, gitiles_prefix, ui_dirpath):
  templateLoader = jinja2.FileSystemLoader(os.path.join(THIS_DIR, 'templates'))
  templateEnv = jinja2.Environment(loader=templateLoader)
  index_template = templateEnv.get_template('antibody_ui_all.jinja')
  tbr_by_user_template = templateEnv.get_template('tbr_by_user.jinja')

  templateVars = {'title' : 'Potentially Suspicious Commits to Chromium',
                  'description' : 'List of commits with a TBR but no lgtm',
                  'antibody_main_link' : ANTIBODY_UI_MAIN_NAME,
                  'tbr_by_user_link' : TBR_BY_USER_NAME,
                  'page_header_text' : "All Potentially Suspicious Commits",
                  'to_be_reviewed' : "To be reviewed by user",
                  'table_headers' : ['git_hash', 'rietveld_url', 
                                     'request_timestamp'],
                  'suspicious_commits' : suspicious_commits_data,
                  'gitiles_prefix' : gitiles_prefix,
                 }
  with open(os.path.join(ui_dirpath, ANTIBODY_UI_MAIN_NAME), 'wb') as f:
    f.write(index_template.render(templateVars)) 

  with open(os.path.join(ui_dirpath, TBR_BY_USER_NAME), 'wb') as f:
    f.write(tbr_by_user_template.render(templateVars)) 


def get_tbr_by_user(cc, dirpath=THIS_DIR):
  cc.execute('SELECT g.git_hash, g.tbr, r.review_url, r.request_timestamp '
             'FROM git g, rietveld r WHERE g.git_hash = r.git_hash '
             'AND r.lgtm <> "1"')
  all_tbr_data = cc.fetchall()

  tbr_blame_dict = {}
  for git_hash, reviewers, url, time in all_tbr_data:
    reviewers = reviewers.split(',')
    for reviewer in reviewers:
      reviewer = reviewer.strip().split('@')
      tbr_blame_dict.setdefault(reviewer[0], []).append([git_hash, url, time])
  # TODO (ksho): read gitiles_prefix from git table once schema changes
  tbr_data = {
      "by_user" : tbr_blame_dict,
      "gitiles_prefix" : "https://chromium.googlesource.com/infra/infra/+/"} 
  with open(os.path.join(dirpath, 'tbr_by_user.json'), 'wb') as f:
    f.write(json.dumps(tbr_data))