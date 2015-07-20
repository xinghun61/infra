# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Testable functions for Antibody."""

import jinja2
import json
import logging
import os
import shutil
import time

import infra.tools.antibody.cloudsql_connect as csql

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
ANTIBODY_UI_MAIN_NAME = 'index.html'
TBR_BY_USER_NAME = 'tbr_by_user.html'

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
  parser.add_argument('--since', '-s', default='01-01-2014',
                      help="parse all git commits after this date"
                           "format as YYYY-MM-DD")


def setup_antibody_db(cc, filename):  # pragma: no cover
  csql.execute_sql_script_from_file(cc, filename)


def generate_antibody_ui(suspicious_commits_data, gitiles_prefix, ui_dirpath):
  template_loader = jinja2.FileSystemLoader(os.path.join(THIS_DIR, 'templates'))
  template_env = jinja2.Environment(loader=template_loader)
  index_template = template_env.get_template('antibody_ui_all.jinja')
  tbr_by_user_template = template_env.get_template('tbr_by_user.jinja')

  template_vars = {
      'title' : 'Potentially Suspicious Commits',
      'description' : 'List of commits with a TBR but no lgtm',
      'antibody_main_link' : ANTIBODY_UI_MAIN_NAME,
      'tbr_by_user_link' : TBR_BY_USER_NAME,
      'generation_time' : time.strftime("%a, %d %b %Y %H:%M:%S",
                                        time.gmtime()),
      'page_header_text' : "All Potentially Suspicious Commits",
      'to_be_reviewed' : "To be reviewed by user",
      'num_tbr_no_lgtm': len(suspicious_commits_data),
      'num_no_review_url': 42,
      'blank_TBR': 3,
      'table_headers' : ['git_hash', 'rietveld_url', 
                         'request_timestamp'],
      'suspicious_commits' : suspicious_commits_data,
      'gitiles_prefix' : gitiles_prefix,
  }
  with open(os.path.join(ui_dirpath, ANTIBODY_UI_MAIN_NAME), 'wb') as f:
    f.write(index_template.render(template_vars))

  with open(os.path.join(ui_dirpath, TBR_BY_USER_NAME), 'wb') as f:
    f.write(tbr_by_user_template.render(template_vars))

  try:  # pragma: no cover
    if (ui_dirpath != THIS_DIR):  # pragma: no cover
      shutil.rmtree(os.path.join(ui_dirpath, 'static'))
  except OSError, e:  # pragma: no cover
    if e.errno == 2:  # [Errno 2] No such file or directory
      pass
    else:
      raise
  if (ui_dirpath != THIS_DIR):  # pragma: no cover
    shutil.copytree(os.path.join(THIS_DIR, 'static'),
                    os.path.join(ui_dirpath, 'static'))


def get_tbr_by_user(tbr_no_lgtm, gitiles_prefix, output_dirpath):
  # tbr_no_lgtm: review_url, request_timestamp, hash, people_email_address
  tbr_blame_dict = {}
  for url, timestamp, git_hash, reviewer in tbr_no_lgtm:
    reviewer = reviewer.strip().split('@')
    timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    tbr_blame_dict.setdefault(reviewer[0], []).append(
        [git_hash, url, timestamp])
  tbr_data = {
      "by_user" : tbr_blame_dict,
      "gitiles_prefix" : gitiles_prefix,
  }
  with open(os.path.join(output_dirpath, 'tbr_by_user.json'), 'wb') as f:
    f.write(json.dumps(tbr_data))


def get_gitiles_prefix(git_checkout_path):
  with open(os.path.join(git_checkout_path, 'codereview.settings'), 'r') as f:
    lines = f.readlines()
  for line in lines:  
    if line.startswith('VIEW_VC:'):
      return line[len('VIEW_VC:'):].strip()
  # TODO (ksho): implement more sophisticated solution if codereview.settings
  # does not contain VIEW_VC
  return None
