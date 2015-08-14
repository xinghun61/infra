# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import datetime
import dateutil.parser
import pytz
import re
import subprocess

import infra.tools.antibody.cloudsql_connect as csql
import infra.tools.antibody.code_review_parse as crp
from infra.tools.antibody.diff_comparer import get_diff_comparison_score


def read_commit_info(git_checkout_path, commits_after_date,
                     git_log_format=('%H', '%b', '%ae',
                                     '%ci', '%f')):  # pragma: no cover
  """Read commit messages and other information

  Args:
    git_checkout_path(str): path to a local git checkout
    git_log_format(str): formatting directives passed to git log --format

  Return:
    log(str): output of git log
  """
  git_log_format = '%x1f'.join(git_log_format) + '%x1e'
  log = subprocess.check_output(['git', 'log', 'master',
      '--format=%s' % git_log_format, '--after=%s' % commits_after_date],
      cwd=git_checkout_path)
  return log


def parse_commit_info(git_log,
                      git_commit_fields=('id', 'body', 'author',
                                         'timestamp', 'subject')):
  """Seperates the various parts of git commit messages

  Args:
    git_log(str): git commits as --format='%H%x1f%b%xlf%ae%xlf%ci%xlf%s%x1e'
    git_commit_fields(tuple): labels for the different components of the
                              commit messages corresponding to the --format

  Return:
    git_log_dict(list): list of dictionaries each corresponding to the parsed
                        components of a single commit message
  """
  git_log_cmds = git_log.strip('\n\x1e').split("\x1e")
  git_log_rows = [row.strip().split("\x1f") for row in git_log_cmds]
  git_log_dict = [dict(zip(git_commit_fields, row)) for row in git_log_rows]
  return git_log_dict


def get_bug_url(git_line):  # pragma: no cover
  bug_url = None
  bug_match = (re.match(r'^BUG=https?://code.google.com/p/(?:chromium'
                        '|rietveld)/issues/detail?id=(\d+)', git_line)
               or re.match(r'^BUG=https?://crbug.com/(\d+)', git_line)
               or re.match(r'^BUG=chromium:(\d+)', git_line)
               or re.match(r'^BUG=(\d+)', git_line))
  if bug_match:
    bug_url = bug_match.group(1)
  return bug_url


def get_tbr(git_line):  # pragma: no cover
  tbr = None
  if git_line.startswith('TBR='):
    if len(git_line) > 4:
      tbr = git_line[4:]
      tbr = [x.strip().split('@')[0] for x in tbr.split(',')]
    else:
      # identifies a blank tbr (TBR= )
      tbr = ['NOBODY']
  return tbr


def url_cleaner(url):  # pragma: no cover
  clean_url = url.strip(' .,()<>:')
  if 'https' not in clean_url:
    clean_url = 'https://' + clean_url
  return clean_url


# TODO: target a required perfect review diff to git diff match accuracy for
# all code review instances to assert a valid review url to add to the table,
# else no review url. This would gurantee that if there were a difference
# between the git diff actually commited and the corresponding diff at the
# review url, it would be investigated to minimize the chances of a barely
# perceptible malicious insertion/deletion of a few lines.
def get_review_url(git_commit, git_checkout_path, cc):  # pragma: no cover
  """Examines all the review urls in a commit to find the most likely review
  url for that commit, and takes one of three actions based on the url type:
    - unblocked rietveld instance: the rietveld diff and git diff are compared
                                   and given a similarity score
    - blocked rietveld instance: internal google and considered trusted
                                 e.g. chromereviews.googleplex.com
    - gerrit instance: currently unable to access a diff suitable for
                       comparison
  Chooses the best url (if at least one strong option is identified) based on:
    1. a review url prefaced with a comment indicating that it is a review url
       (preferred because comparing the diffs is computationaly expensive)
    2. a review url with a similarity score > 0.90
    3. None

  Args:
    git_commit(dict): a commit message parsed into a dictionary
    git_checkout_path(str): path to a local git checkout
    cc: Cloud SQL cursor

  Return:
    top_scored_url(str): the review url identified to be the best match else
                         None
  """
  review_urls = []
  url_matches = [
      'chromiumcodereview-hr.appspot.com',
      'chromiumcodereview.appspot.com',
      'codereview.appspot.com',
      'codereview.chromium.org',
      'skia-codereview-staging.appspot.com',
      'skia-codereview-staging2.appspot.com',
      'skia-codereview-staging3.appspot.com',
  ]
  inaccessable = [
      'chromereviews.googleplex.com',
      'chromium-review.googlesource.com',
  ]
  for line in git_commit['body'].split('\n'):
    for word in line.split():
      if any(url in word for url in inaccessable) \
          or any(url in word for url in url_matches):
        url = basic_review_url_identifier(line)
        if url:
          good_url = url_cleaner(url)
          return good_url
      if any(url in word for url in url_matches) and 'diff' not in word:
        good_url = url_cleaner(word)
        review_urls.append(good_url)
  top_scored_url = [None, 0]
  for url in review_urls:
    score = get_diff_comparison_score(git_commit['id'], url,
                                      git_checkout_path, cc)
    if score >= top_scored_url[1]:
      top_scored_url = [url, score]
  if top_scored_url[1] > 0.90:
    return top_scored_url[0]
  return None


def basic_review_url_identifier(git_line):  # pragma: no cover
  """Used to check the basic case in which a review url is prefaced with some
  known indicator in the commit message

  Args:
    git_line(str): a line in the git commit body

  Returns:
    review_url(str): a review url if one is found
  """
  review_url = None
  if re.match(r'^Review: .+$', git_line):
    review_url = git_line[8:]
  elif re.match(r'^Review URL: .+$', git_line):
    review_url = git_line[12:]
  elif re.match(r'^Code review URL: .+$', git_line):
    review_url = git_line[17:]
  elif re.match(r'^Reviewed-on: .+$', git_line):
    review_url = git_line[13:]
  if review_url:
    return review_url.strip(' .,()<>:')
  return None


# TODO(keelerh): populate project table and add project ids (currently auto
# inserts 0 as the project id)
def get_features_for_git_commit(git_commit, git_checkout_path, cc):
  """Retrieves the git commit features

  Arg:
    git_commit(dict): a commit message parsed into a dictionary

  Return:
    (tuple): relevant features extracted from the commit message
  """
  git_hash = git_commit['id']
  dt = dateutil.parser.parse(git_commit['timestamp']).astimezone(pytz.UTC)
  # dt is a datetime object with timezone info
  timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
  subject = git_commit['subject']
  bug_url = None
  for line in git_commit['body'].strip(',').split('\n'):
    bug_url = get_bug_url(line) or bug_url
  review_URL = get_review_url(git_commit, git_checkout_path, cc)
  return (git_hash, bug_url, timestamp, review_URL, 0, subject)


def get_features_for_commit_people(git_commit):
  """Retrieves the people associated with a git commit

  Arg:
    git_commit(dict): a commit message parsed into a dictionary

  Return:
    (tuple): relevant people and type extracted from the commit
  """
  curr_time = datetime.datetime.utcnow()
  git_hash = git_commit['id']
  author = git_commit['author'].split('@')[0]
  people_rows = [(author, git_hash, curr_time, 'author')]
  TBR = None
  for line in git_commit['body'].split('\n'):
    TBR = get_tbr(line) or TBR
  if TBR is not None:
    for person in TBR:
      people_rows.append((person, git_hash, curr_time, 'tbr'))
  return people_rows


def parse_commit_message(git_log, git_checkout_path, cc):  # pragma: no cover
  """Extracts features from the commit message

  Arg:
    git_log(list): all commits in a git log parsed as dictionaries

  Return:
    commits(list): all commits represented by a tuple with the
                   extracted commit features
  """
  commits = []
  for commit in git_log:
    commits.append(get_features_for_git_commit(commit, git_checkout_path, cc))
  return commits


def parse_commit_people(git_log):
  """Extracts features associated with the people in a commit

  Arg:
    git_log(list): all commits in a git log parsed as dictionaries

  Return:
    commits(list): all commits represented by a tuple with the
                   extracted features about each associated person
  """
  commits = []
  for commit in git_log:
    associated_people = get_features_for_commit_people(commit)
    uniq_primary_keys = crp.primary_key_uniquifier(associated_people,
        lambda x: (x[0].lower(), x[1], x[3]))
    for tup in uniq_primary_keys:
      commits.append(tup)
  return commits


def write_to_csv(git_commit_filename, git_people_filename, cc,
    git_checkout_path, commits_after_date):  # pragma: no cover
  log_output = read_commit_info(git_checkout_path, commits_after_date)
  log_dict = parse_commit_info(log_output)
  git_commit_output = parse_commit_message(log_dict, git_checkout_path, cc)
  with open(git_commit_filename, 'w') as f:
    for row in git_commit_output:
      # hash|bug_url|timestamp|review_url|project_prj_id|subject
      # VARCHAR(40)|VARCHAR(200)|TIMESTAMP|VARCHAR(200)|INT|VARCHAR(500)
      csv.writer(f).writerow(row)
  commit_people_output = parse_commit_people(log_dict)
  with open(git_people_filename, 'w') as f:
    for row in commit_people_output:
      # people_email_address|git_commit_hash|request_timestamp|type
      # VARCHAR(200)|VARCHAR(40)|TIMESTAMP|VARCHAR(10)
      csv.writer(f).writerow(row)


def upload_to_sql(git_commit_filename, commit_people_filename, cc,
      git_checkout_path, commits_after_date):  # pragma: no cover
  """Writes suspicious git commits to a Cloud SQL database

  Args:
    cc: a cursor for the Cloud SQL connection
    git_checkout_path(str): path to a local git checkout
  """
  write_to_csv(git_commit_filename, commit_people_filename, cc,
      git_checkout_path, commits_after_date)
  csql.write_to_sql_table(cc, commit_people_filename, 'commit_people')
  csql.write_to_sql_table(cc, git_commit_filename, 'git_commit')