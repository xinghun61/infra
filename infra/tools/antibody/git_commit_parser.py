# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import dateutil.parser
import pytz
import re
import subprocess

import infra.tools.antibody.cloudsql_connect as csql

curr_time = datetime.datetime.now()


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


def get_bug_url(git_line):
  bug_url = None
  bug_match = (re.match(r'^BUG=https?://code.google.com/p/(?:chromium'
                        '|rietveld)/issues/detail?id=(\d+)', git_line)
               or re.match(r'^BUG=https?://crbug.com/(\d+)', git_line)
               or re.match(r'^BUG=chromium:(\d+)', git_line)
               or re.match(r'^BUG=(\d+)', git_line))
  if bug_match:
    bug_url = bug_match.group(1)
  return bug_url


def get_tbr(git_line):
  tbr = None
  if git_line.startswith('TBR='):
    if len(git_line) > 4:
      tbr = git_line[4:]
      tbr = [x.strip().split('@')[0] for x in tbr.split(',')]
    else:
      tbr = ['NOBODY']
  return tbr


# TODO(keelerh): scan all review urls in a commit and compare the diffs to
# identify the correct one
def get_review_url(git_line):
  review_url = None
  if re.match(r'^Review: .+$', git_line):
    review_url = git_line[8:]
  elif re.match(r'^Review URL: .+$', git_line):
    review_url = git_line[12:]
  elif re.match(r'^Code review URL: .+$', git_line):
    review_url = git_line[17:]
  elif re.match(r'^Reviewed-on: .+$', git_line):
    review_url = git_line[13:]
  return review_url


def get_features_for_git_commit(git_commit):
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
  bug_url, review_URL = None, None
  for line in git_commit['body'].split('\n'):
    bug_url = get_bug_url(line) or bug_url
    review_URL = get_review_url(line) or review_URL
  return (git_hash, bug_url, timestamp, review_URL, None, subject)


def get_features_for_commit_people(git_commit):
  """Retrieves the people associated with a git commit

  Arg:
    git_commit(dict): a commit message parsed into a dictionary

  Return:
    (tuple): relevant people and type extracted from the commit
  """
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


def parse_commit_message(git_log):
  """Extracts features from the commit message

  Arg:
    git_log(list): all commits in a git log parsed as dictionaries

  Return:
    commits(list): all commits represented by a tuple with the
                   extracted commit features
  """
  commits = []
  for commit in git_log:
    commits.append(get_features_for_git_commit(commit))
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
    for tup in associated_people:
      commits.append(tup)
  return commits


def upload_to_sql(cc, git_checkout_path,
                      commits_after_date):  # pragma: no cover
  """Writes suspicious git commits to a Cloud SQL database

  Args:
    cc: a cursor for the Cloud SQL connection
    git_checkout_path(str): path to a local git checkout
  """
  log_output = read_commit_info(git_checkout_path, commits_after_date)
  log_dict = parse_commit_info(log_output)
  git_commit_output = parse_commit_message(log_dict)
  commit_people_output = parse_commit_people(log_dict)
  csql.write_to_git_commit(cc, git_commit_output)
  csql.write_to_commit_people(cc, commit_people_output)


def get_urls_from_git_commit(cc):  # pragma: no cover
  """Accesses Cloud SQL instance to find the review urls of the stored
     commits that have a TBR

  Arg:
    cc: a cursor for the Cloud SQL connection

  Return:
    commits_with_review_urls(list): all the commits in the db w/ a TBR
                                    and a review url
  """
  cc.execute("""SELECT git_commit.review_url,
      commit_people.people_email_address, commit_people.type
      FROM commit_people
      INNER JOIN (
        SELECT git_commit_hash, COUNT(*)
        AS c
        FROM commit_people
        WHERE type='tbr'
        GROUP BY git_commit_hash) tbr_count
      ON commit_people.git_commit_hash = tbr_count.git_commit_hash
      INNER JOIN git_commit
      ON commit_people.git_commit_hash = git_commit.hash
      WHERE tbr_count.c <> 0
      AND git_commit.review_url IS NOT NULL
      AND commit_people.type='author'""")
  commits_with_review_urls = cc.fetchall()
  return [x[0] for x in commits_with_review_urls]