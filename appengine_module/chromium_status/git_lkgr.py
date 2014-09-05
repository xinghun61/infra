# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Git LKGR management webpages."""

import json
import logging

from google.appengine.ext import db

from appengine_module.chromium_status.base_page import BasePage
from appengine_module.chromium_status import utils


class Commit(db.Model):  # pylint: disable=W0232
  """Description of a commit, keyed by random integer IDs."""
  # Git hash of this commit. A property so it can be viewed in datastore.
  git_hash = db.StringProperty()
  # Git commit position for this commit (required for sorting).
  position_ref = db.StringProperty()
  position_num = db.IntegerProperty()
  # Time at which this commit was set as the LKGR.
  date = db.DateTimeProperty(auto_now_add=True)


class Commits(BasePage):
  """Displays the Git LKGR history page containing the last 100 LKGRs."""

  @utils.requires_read_access
  def get(self):
    """Returns information about the history of LKGR."""
    limit = int(self.request.get('limit', 100))
    commits = Commit.all().order(
        '-position_num').order('position_ref').fetch(limit)

    if self.request.get('format') == 'json':
      self.response.headers['Content-Type'] = 'application/json'
      self.response.headers['Access-Control-Allow-Origin'] = '*'
      data = json.dumps([commit.AsDict() for commit in commits])
      self.response.out.write(data)
      return

    template_values = self.InitializeTemplate('Chromium Git LKGR History')
    page_value = {'commits': commits, 'limit': limit}
    template_values.update(page_value)
    self.DisplayTemplate('commits.html', template_values)

  @utils.requires_write_access
  def post(self):
    """Adds a new revision status."""
    git_hash = self.request.get('hash')
    position_ref = self.request.get('position_ref')
    position_num = int(self.request.get('position_num'))
    if git_hash and position_ref and position_num:
      obj = Commit(git_hash=git_hash,
                   position_ref=position_ref, position_num=position_num)
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
    commit = Commit.all().order('-position_num').order('position_ref').get()
    if commit:
      self.response.out.write(commit.git_hash)
    else:
      logging.error('OMG There\'s no git-lkgr!?')
      self.abort(404)


def bootstrap():
  Commit.get_or_insert('dummy-commit', git_hash='0'*40,
                       position_ref='refs/heads/master', position_num=0)
