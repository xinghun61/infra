# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import subprocess
import httplib2

import infra.tools.antibody.code_review_parse as crp


def get_git_diff(commit_hash, git_checkout_path):  # pragma: no cover
  """Reads the diff for a specified commit

  Args:
    commit_hash(str): a git hash
    git_checkout_path(str): path to a local git checkout

  Return:
    diff(list): the lines in the git diff
  """
  diff = subprocess.check_output(['git', 'show', commit_hash],
      cwd=git_checkout_path)
  lines = diff.splitlines()
  return lines


def get_rietveld_diff(rietveld_url, cc, git_checkout_path):  # pragma: no cover
  """Reads the diff for a specified commit

  Args:
    commit_hash(str): a git hash
    cc: a cursor for the Cloud SQL connection
    git_checkout_path(str): path to a local git checkout

  Return:
    diff(list): the lines in the rietveld diff
  """
  canonical_url = crp.to_canonical_review_url(rietveld_url)
  json_data = crp.extract_code_review_json_data(
      canonical_url, cc, git_checkout_path)
  for message in json_data['messages']:
    if ('committed' in message['text'].lower() and
        (json_data['closed'] or message['issue_was_closed'])):
      if 'patchset' in message:
        patchset = message['patchset']
      elif message['text'] and 'patchset' in message['text']:
        for word in message['text'].split():
          if word.startswith('(id:'):
            patchset = word[4:].strip(')')
      else:
        # no commited patchset id found so diff comparison cannot happen
        return []
      url_components = re.split('(https?:\/\/)([\da-z\.-]+)', canonical_url)
      diff_url = '%s%s/download/issue%s_%s.diff' % (url_components[1],
                  url_components[2], url_components[3][1:], patchset)
      h = httplib2.Http(".cache")
      _, content = h.request(diff_url, "GET")
      lines = content.splitlines()
      return lines
  return []


def get_diff_comparison_score(git_commit, review_url, git_checkout_path,
                              cc):  # pragma: no cover
  """Reads the diff for a specified commit

  Args:
    git_commit(str): a commit hash
    review_url(str): a rietveld review url
    git_checkout_path(str): path to a local git checkout
    cc: a cursor for the Cloud SQL connection


  Return:
    score(float): a score in [0,1] where 0 is no similarity and 1 is a perfect
                  match
  """
  git_diff = get_git_diff(git_commit, git_checkout_path)
  comparable_git_diff = [x for x in git_diff if x.startswith('+') \
      or x.startswith('-')]
  rietveld_diff = get_rietveld_diff(review_url, cc, git_checkout_path)
  comparable_rietveld_diff = [x for x in rietveld_diff if x.startswith('+') \
      or x.startswith('-')]
  matching = list(set(comparable_git_diff) - set(comparable_rietveld_diff))
  total = max(len(comparable_git_diff), len(comparable_rietveld_diff))
  score = 1 - float(len(matching)) / total if total != 0 else 0
  return score