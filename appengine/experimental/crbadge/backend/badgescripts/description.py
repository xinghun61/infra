# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Examines commit descriptions and assign badges for each person."""

from collections import defaultdict
from datetime import datetime
import json
import os
import sys


_THIRD_PARTY_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                os.path.pardir, os.path.pardir, 'third_party')
sys.path.insert(0, _THIRD_PARTY_DIR)

from local_libs.git_checkout.local_git_repository import LocalGitRepository


_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'


class Description(object):
  def __init__(self):
    self.blank = 0
    self.one_word = 0
    self.long_desc = 0
    self.short_desc = 0
    self.spaces = 0

  def ToDict(self):
    return {
      'blank': self.blank,
      'one_word': self.one_word,
      'long_desc': self.long_desc,
      'short_desc': self.short_desc,
      'spaces': self.spaces
    }

  @classmethod
  def FromDict(cls, data):
    instance = cls()
    for key, value in data.iteritems():
      setattr(instance, key, value)
    return instance


def _DescriptionsToDict(results):
  new_dict = {}
  for key, result in results.iteritems():
    new_dict[key] = result.ToDict()
  return new_dict


def _GetResults(existing_data, commits):
  results = defaultdict(Description, existing_data)
  for commit in commits:
    author = commit.author.email
    result = results[author]
    messages = commit.message.split('\n\n', 1)

    if len(messages) < 2:
      # No \n\n in message, no description.
      result.blank += 1
      continue

    description = messages[1]
    if len(description) < 50:
      # Short description.
      result.short_desc += 1
    elif len(description) > 1000:
      # Long description.
      result.long_desc += 1

    if '     ' in description:
      # Description has 5 spaces or more.
      result.spaces += 1

    if len(description.split()) == 0:
      # Empty description with white spaces.
      result.blank += 1
    elif len(description.split()) == 1:
      # One word.
      result.one_word += 1

  with open('tmp/descriptions', 'w') as outf:
    outf.write(json.dumps(_DescriptionsToDict(results), indent=2))

  return results


def _GetExistingData():
  data = {}
  if not os.path.isfile('tmp/descriptions'):
    return data

  with open('tmp/descriptions') as inf:
    data = json.loads(inf.read())

    existing_data = {}
    for name, description in data.iteritems():
      existing_data[name] = Description.FromDict(description)

    return existing_data


def _GetStartRevision():
  if not os.path.isfile('tmp/d_end_revision'):
    return None
  with open('tmp/d_end_revision') as inf:
    return inf.read()


def _GenerateResults(results):
  blank_data = []
  one_word_data = []
  long_data = []
  short_data = []
  spaces_data = []
  for email, result in results.iteritems():
    if result.blank > 5:
      blank_data.append({
      'email': email,
      'value': result.blank})
    if result.one_word > 5:
      one_word_data.append({
        'email': email,
        'value': result.one_word})
    if result.long_desc > 5:
      long_data.append({
        'email': email,
        'value': result.long_desc})
    if result.short_desc > 5:
      short_data.append({
        'email': email,
        'value': result.short_desc})
    if result.spaces > 5:
      spaces_data.append({
        'email': email,
        'value': result.spaces})

  all_data = [
      {
        'badge_name': 'code-number_of_descriptions_blank',
        'data': blank_data
      },
      {
        'badge_name': 'code-number_of_descriptions_one_word',
        'data': one_word_data
      },
      {
        'badge_name': 'code-number_of_descriptions_over_1000_charss',
        'data': long_data
      },
      {
        'badge_name': 'code-number_of_descriptions_under_50_chars',
        'data': short_data
      },
      {
        'badge_name': 'code-number_of_descriptions_with_5_consec_spaces',
        'data': spaces_data
      },
  ]
  return all_data


def _SaveLastCheckedRevision(git_repo, end_revision):
  if end_revision == 'HEAD':
    change_log = git_repo.GetChangeLog(end_revision)
    end_revision = change_log.revision

  with open('tmp/d_end_revision', 'w') as outf:
    outf.write(end_revision)

if __name__ == '__main__':
  git_repo = LocalGitRepository(
      'https://chromium.googlesource.com/chromium/src.git')

  existing_data = _GetExistingData()

  start_revision = _GetStartRevision() or 'a5068f5fa11005232bc4383c54f6af230f9392fb'
  end_revision = 'HEAD'

  commits = git_repo.GetChangeLogs(start_revision, end_revision)
  results = _GetResults(existing_data, commits)


  _SaveLastCheckedRevision(git_repo, end_revision)
  print json.dumps(_GenerateResults(results), indent=4)