# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Git LKGR management webpages."""

import json
import logging

from google.appengine.ext import db

from base_page import BasePage
import utils


class Commit(db.Model):  # pylint: disable=W0232
  """Description of a commit, keyed by the git hash."""
  # Git generation number for this commit (required for sorting).
  gen_number = db.IntegerProperty()
  # Time at which this commit was set as the LKGR.
  date = db.DateTimeProperty(auto_now_add=True)


class Commits(BasePage):
  """Displays the Git LKGR history page containing the last 100 LKGRs."""

  @utils.requires_read_access
  def get(self):
    """Returns information about the history of LKGR."""
    limit = int(self.request.get('limit', 100))
    commits = Commit.all().order('-gen_number').fetch(limit)
    data = [commit.AsDict() for commit in commits]
    for i, commit in enumerate(data[:-1]):
      delta = commit['gen_number'] - data[i+1]['gen_number']
      commit['delta'] = delta
    data[-1]['delta'] = 0

    if self.request.get('format') == 'json':
      self.response.headers['Content-Type'] = 'application/json'
      self.response.headers['Access-Control-Allow-Origin'] = '*'
      self.response.out.write(json.dumps(data))
      return

    page_value = {'commits': data}
    template_values = self.InitializeTemplate('Chromium Git LKGR History')
    template_values.update(page_value)
    self.DisplayTemplate('commits.html', template_values)

  @utils.requires_write_access
  def post(self):
    """Adds a new revision status."""
    git_hash = self.request.get('git_hash')
    gen_number = self.request.get('gen_number')
    if git_hash and gen_number:
      gen_number = int(gen_number)
      obj = Commit(git_hash=git_hash, gen_number=gen_number)
      obj.put()
    else:
      self.abort(400)


class LastKnownGoodRevisionGIT(BasePage):
  """Displays the /git-lkgr page."""

  @utils.requires_read_access
  def get(self):
    """Look for the latest successful revision and return it."""
    self.response.headers['Cache-Control'] =  'no-cache, private, max-age=5'
    self.response.headers['Content-Type'] = 'text/plain'
    commit = Commit.all().order('-gen_number').get()
    if commit:
      self.response.out.write(commit.git_hash)
    else:
      logging.error('OMG There\'s no git-lkgr!?')
      self.abort(404)


def bootstrap():
  Commit.get_or_insert('0'*40, gen_number=-1)
