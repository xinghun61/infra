# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import subprocess

import infra.tools.antibody.cloudsql_connect as csql


def read_commit_info(git_log_format=('%H', '%b'), 
                     year=2011):  # pragma: no cover
    git_log_format = '%x1f'.join(git_log_format) + '%x1e'
    log = subprocess.check_output(['git', 'log', 
                                   '--format=%s' % git_log_format,
                                   '--after=%s' % year])
    return log


def parse_commit_info(git_log,
                      git_commit_fields=('id', 'body')): 
    """Git log as --format='%H%x1f%b%x1e' and returns a list of dictionaries"""
    git_log_cmds = git_log.strip('\n\x1e').split("\x1e")
    git_log_rows = [row.strip().split("\x1f") for row in git_log_cmds]
    git_log_dict = [dict(zip(git_commit_fields, row)) for row in git_log_rows]
    return git_log_dict


def is_commit_suspicious(git_commit): 
    for line in git_commit['body'].split('\n'):
        if line.startswith('TBR=') and len(line) > 4:
            return True
        if get_review_url(line):
            return False
    return True


def get_bug_num(git_line):
    bug_number = None
    bug_match = (re.match(r'^BUG=https?://code.google.com/p/(?:chromium'
                          '|rietveld)/issues/detail?id=(\d+)', git_line)
                 or re.match(r'^BUG=https?://crbug.com/(\d+)', git_line)
                 or re.match(r'^BUG=chromium:(\d+)', git_line)
                 or re.match(r'^BUG=(\d+)', git_line))
    if bug_match:
        bug_number = bug_match.group(1)
    return bug_number


def get_tbr(git_line):
    tbr = None
    if git_line.startswith('TBR=') and len(git_line) > 4:
        tbr = git_line[4:]
    return tbr


def get_review_url(git_line):
    review_url = None
    if re.match(r'^Review:.+$', git_line):
        review_url = git_line[8:]
    elif re.match(r'^Review URL:.+$', git_line):
        review_url = git_line[12:]
    elif re.match(r'^Code review URL:.+$', git_line):
        review_url = git_line[17:]
    return review_url


def get_features_from_commit(git_commit): 
    git_hash = git_commit['id']
    bug_num, TBR, review_URL = None, None, None
    for line in git_commit['body'].split('\n'):
        bug_num = get_bug_num(line) or bug_num
        TBR = get_tbr(line) or TBR
        review_URL = get_review_url(line) or review_URL
    return (git_hash, bug_num, TBR, review_URL)


def parse_commit_message(git_log):
    commits = []
    for commit in git_log:
        if is_commit_suspicious(commit):
            commits.append(get_features_from_commit(commit))
    return commits


def upload_git_to_sql(cc):  # pragma: no cover
    log_output = read_commit_info()
    log_dict = parse_commit_info(log_output)
    output = parse_commit_message(log_dict)
    csql.write_to_git_table(cc, output)


def get_urls_from_git_db(cc):
    cc.execute("""SELECT * FROM %s""" % csql.DEFAULT_GIT_TABLE)
    git_data = cc.fetchall()
    commits_with_review_urls = []
    for git_hash, _, _, review_url in git_data:
      if review_url:
        commits_with_review_urls.append((git_hash, review_url))
    return commits_with_review_urls