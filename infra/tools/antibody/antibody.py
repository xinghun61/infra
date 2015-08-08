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
from infra.tools.antibody import compute_stats
from infra.tools.antibody import code_review_parse

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
ANTIBODY_UI_DIRPATH = os.path.join(THIS_DIR, 'antibody_ui')
ANTIBODY_UI_MAIN_NAME = 'index.html'
SEARCH_BY_USER_NAME = 'search_by_user.html'
STATS_NAME = 'stats.html'
LEADERBOARD_NAME = 'leaderboard.html'
TBR_NO_LGTM_NAME = 'tbred_without_lgtm'
NO_REVIEW_URL_NAME = 'without_review_url'
BLANK_TBR_NAME = 'with_blank_tbr'
STATS_7_NAME = 'past_7_days.html'
STATS_30_NAME = 'past_30_days.html'
STATS_ALL_TIME_NAME = 'all_time.html'
# TODO(ksho): make command line arg
REPOSITORIES = ['infra']


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
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
  parser.add_argument('--output-dir-path', '-d', default=ANTIBODY_UI_DIRPATH,
                      help="path to directory in which the ui will be"
                           "generated")
  parser.add_argument('--since', '-s', default='01-01-2015',
                      help="parse all git commits after this date"
                           "format as YYYY-MM-DD")

def setup_antibody_db(cc, filename):  # pragma: no cover
  csql.execute_sql_script_from_file(cc, filename)


def generate_antibody_ui(cc, gitiles_prefix, project_name, since, ui_dirpath, 
                         suspicious_commits):
  template_loader = jinja2.FileSystemLoader(os.path.join(THIS_DIR, 'templates'))
  template_env = jinja2.Environment(loader=template_loader)
  template_vars_all = {
      'antibody_main_link': ANTIBODY_UI_MAIN_NAME,
      'search_by_user_link': SEARCH_BY_USER_NAME,
      'stats_link': STATS_NAME,
      'leaderboard_link': LEADERBOARD_NAME,
      'tbr_no_lgtm_link': TBR_NO_LGTM_NAME,
      'no_review_url_link': NO_REVIEW_URL_NAME,
      'blank_tbr_link': BLANK_TBR_NAME,
      'stats_7_link': STATS_7_NAME,
      'stats_30_link': STATS_30_NAME,
      'stats_all_time_link': STATS_ALL_TIME_NAME,
      'generation_time' : time.strftime("%a, %d %b %Y %H:%M:%S",
                                        time.gmtime()),
      'page_header_text': "Antibody",
      'by_user': "Search by user",
      'stats': 'Stats',
      'leaderboard': 'Leaderboard',
      'gitiles_prefix': gitiles_prefix,
      'gitiles_link': (gitiles_prefix[:-3]) if (
          gitiles_prefix[-3:] == '/+/') else '',
      'all_repos': REPOSITORIES,
      'curr_repo': project_name,
      'since': since,
      'feedback_link': 'https://code.google.com/p/chromium/issues/entry?'
          'template=Build%20Infrastructure&labels=Restrict-View-Google,Infra-'
          'Monitoring,Infra&summary=%5BBrief%20description%20of%20problem%20or'
          '%20feedback%20for%20Antibody%5D&comment=Please%20provide%20the%20'
          'details%20for%20your%20request%20here.&cc=pgervais@chromium.org,'
          '%20hinoka@chromium.org,%20keelerh@google.com,%20ksho@google.com',
      'navbar_items': [
          [ANTIBODY_UI_MAIN_NAME, 'home_nav', 'Commits'],
          [SEARCH_BY_USER_NAME, 'search_nav', 'Search by User'],
          [STATS_NAME, 'stats_nav', 'Stats'],
          [LEADERBOARD_NAME, 'leaderboard_nav', 'Leaderboard'],
      ]
  }

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


  repo_dirpath = os.path.join(ui_dirpath, project_name)
  if not os.path.exists(repo_dirpath):  # pragma: no cover
      os.makedirs(repo_dirpath)
  generate_stats_files(cc, repo_dirpath)
  get_commits_by_user(cc, gitiles_prefix, repo_dirpath)
  generate_homepage(suspicious_commits, template_env, template_vars_all, 
                    repo_dirpath)
  generate_tbr_page(template_env, template_vars_all, repo_dirpath)
  generate_stats_page(template_env, template_vars_all, repo_dirpath)
  generate_leaderboard_page(template_env, template_vars_all, repo_dirpath)
  generate_time_period_stats_pages(template_env, template_vars_all,
                                   repo_dirpath)


def generate_homepage(suspicious_commits, template_env, template_vars_all, 
                      ui_dirpath):
  index_template = template_env.get_template('antibody_ui_all.jinja')
  with open(os.path.join(ui_dirpath, 'all_monthly_stats.json')) as f:
    data = json.load(f)
  stats_7_day = data['7_days']
  template_vars = {
      'title' : 'Antibody',
      'curr_page_link': ANTIBODY_UI_MAIN_NAME,
      'curr_page_id': 'home_body',
      'blank_TBR': stats_7_day['blank_tbr'],
      'num_tbr_no_lgtm': stats_7_day['tbr_no_lgtm'],
      'num_no_review_url': stats_7_day['no_review_url'],
      'suspicious_commits': suspicious_commits,
      'table_headers' : ['Commit Timestamp (UTC)', 'Code Review',
                         'Git Commit Hash'],
  }
  template_vars.update(template_vars_all)
  with open(os.path.join(ui_dirpath, ANTIBODY_UI_MAIN_NAME), 'wb') as f:
    f.write(index_template.render(template_vars))


def generate_tbr_page(template_env, template_vars_all, ui_dirpath):
  search_by_user_template = template_env.get_template('search_by_user.jinja')
  template_vars = {
      'title' : 'TBR by User',
      'curr_page_link': SEARCH_BY_USER_NAME,
      'curr_page_id': 'search_body',
  }
  template_vars.update(template_vars_all)
  with open(os.path.join(ui_dirpath, SEARCH_BY_USER_NAME), 'wb') as f:
    f.write(search_by_user_template.render(template_vars))


def generate_stats_page(template_env, template_vars_all, ui_dirpath):
  stats_template = template_env.get_template('stats.jinja')
  with open(os.path.join(ui_dirpath, 'all_monthly_stats.json')) as f:
    data = json.load(f)
  template_vars = {
      'title' : 'Antibody Stats',
      'curr_page_link': STATS_NAME,
      'curr_page_id': 'stats_body',
      'table_headers': ['Git Hash', 'Review URL', 'Commit Timestamp (UTC)'],
  }
  stats_all = [
      [data['7_days'], 'total_stats_7_day', 'indiv_stats_7_day'],
      [data['30_days'], 'total_stats_30_day', 'indiv_stats_30_day'],
      [data['all_time'], 'total_stats_all_time', 'indiv_stats_all_time'],
  ]
  total_categories_keys = [
      ['"Suspicious":Total Commits', 'suspicious_to_total_ratio'],
      ['Total Commits', 'total_commits'],
  ]
  for stats, key, _ in stats_all:
    template_vars[key] = [[x[0], stats[x[1]]] for x in total_categories_keys]
  indiv_categories_keys = [
      ['TBR without LGTM', 'tbr_no_lgtm', TBR_NO_LGTM_NAME],
      ['Without review url', 'no_review_url', NO_REVIEW_URL_NAME],
      ['Blank TBR', 'blank_tbr', BLANK_TBR_NAME],
  ]
  for stats, _, key in stats_all:
    template_vars[key] = [[x[0], stats[x[1]], x[2]] 
                          for x in indiv_categories_keys]
  template_vars.update(template_vars_all)
  with open(os.path.join(ui_dirpath, STATS_NAME), 'wb') as f:
    f.write(stats_template.render(template_vars))


def generate_leaderboard_page(template_env, template_vars_all, ui_dirpath):
  leaderboard_template = template_env.get_template('leaderboard.jinja')
  template_vars = {
      'title' : 'Hall of Shame',
      'curr_page_link': LEADERBOARD_NAME,
      'curr_page_id': 'leaderboard_body',
  }
  template_vars.update(template_vars_all)
  with open(os.path.join(ui_dirpath, LEADERBOARD_NAME), 'wb') as f:
    f.write(leaderboard_template.render(template_vars))


def generate_time_period_stats_pages(template_env, template_vars_all, 
                                     ui_dirpath):
  time_period_pages_info = [
      [STATS_7_NAME, 'Commits in the past 7 days', '7_days'],
      [STATS_30_NAME, 'Commits in the past 30 days', '30_days'],
      [STATS_ALL_TIME_NAME, 'Commits since ' + template_vars_all['since'],
       'all_time'],
  ]
  with open(os.path.join(ui_dirpath, 'all_monthly_stats.json'), 'r') as f:
    commit_data = json.load(f)
  time_period_template = template_env.get_template('time_period_stats.jinja')
  for time_period_page in time_period_pages_info:
    time_period_commits = commit_data[time_period_page[2]]
    template_vars = {
      'title' : time_period_page[1],
      'curr_page': time_period_page[1],
      'time_period_header_name': time_period_page[1],
      'table_headers': ['Git Commit Hash', 'Code Review',
                        'Commit Timestamp (UTC)'],
      'table_headers_no_review': ['Git Commit Hash', 'Git Subject',
                                  'Commit Timestamp (UTC)'],
      'tbr_no_lgtm': time_period_commits['tbr_no_lgtm_commits'],
      'no_review_url': time_period_commits['no_review_url_commits'],
      'blank_tbr': time_period_commits['blank_tbr_commits'],
    }
    template_vars.update(template_vars_all)
    with open(os.path.join(ui_dirpath, time_period_page[0]), 'wb') as f:
      f.write(time_period_template.render(template_vars))


def get_commits_by_user(cc, gitiles_prefix, output_dirpath):
  # tbr_no_lgtm: review_url, request_timestamp, subject, people_email_address,
  # hash
  tbr_blame_dict = {}
  commits_tbred_to_user = code_review_parse.get_tbr_no_lgtm(cc, 'tbr')
  commits_authored_by_user = code_review_parse.get_tbr_no_lgtm(cc, 'author')
  for url, timestamp, subject, reviewer, git_hash in commits_tbred_to_user:
    tbr_blame_dict.setdefault(reviewer, {'tbr':[], 'author':[]})['tbr'].append(
        [subject, url, timestamp, git_hash, 'TBR'])
  for url, timestamp, subject, reviewer, git_hash in commits_authored_by_user:
    tbr_blame_dict.setdefault(reviewer, {'tbr':[],
                                         'author':[]})['author'].append(
        [subject, url, timestamp, git_hash, 'Author'])
  tbr_data = {
      "by_user" : tbr_blame_dict,
      "gitiles_prefix" : gitiles_prefix,
  }
  with open(os.path.join(output_dirpath, 'search_by_user.json'), 'wb') as f:
    f.write(json.dumps(tbr_data))


def generate_stats_files(cc, output_dirpath):  # pragma: no cover
  compute_stats.all_time_leaderboard(cc,
      os.path.join(output_dirpath, 'all_time_leaderboard.json'))
  compute_stats.past_month_leaderboard(cc,
      os.path.join(output_dirpath, 'past_month_leaderboard.json'))
  compute_stats.all_monthly_stats(cc,
      os.path.join(output_dirpath, 'all_monthly_stats.json'))


def get_gitiles_prefix(git_checkout_path):
  with open(os.path.join(git_checkout_path, 'codereview.settings'), 'r') as f:
    lines = f.readlines()
  for line in lines:
    if line.startswith('VIEW_VC:'):
      return line[len('VIEW_VC:'):].strip()
  # TODO(ksho): implement more sophisticated solution if codereview.settings
  # does not contain VIEW_VC
  return None


def get_project_name(git_checkout_path):
  with open(os.path.join(git_checkout_path, 'codereview.settings'), 'r') as f:
    lines = f.readlines()
  for line in lines:
    if line.startswith('PROJECT:'):
      return line[len('PROJECT:'):].strip()
  # TODO (ksho): implement more sophisticated solution if codereview.settings
  # does not contain PROJECT
  return None