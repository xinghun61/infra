# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""LKGR management webpages."""

import json
import logging

from google.appengine.ext import db

from base_page import BasePage
import utils


class Revision(db.Model):  # pylint: disable=W0232
  """Description for the revisions table."""
  # The revision for which we save a status.
  revision = db.IntegerProperty(required=True)
  # The date when the revision status got added.
  date = db.DateTimeProperty(auto_now_add=True)
  # The success (True)/Failure (False) status of this revision.
  status = db.BooleanProperty(required=True)
  # The steps that caused the failure (if any).
  failed_steps = db.TextProperty()
  # Git hash for this revision
  git_hash = db.StringProperty()
  # Git hash is set
  git_hash_set = db.BooleanProperty(default=False)


class Revisions(BasePage):
  """Displays the revisions page containing the last 100 revisions."""

  def get(self):
    """Returns information about the last revision status."""
    limit = int(self.request.get('limit', 100))
    revisions = Revision.all().order('-revision').fetch(limit)
    if self.request.get('format') == 'json':
      self.response.headers['Content-Type'] = 'application/json'
      self.response.headers['Access-Control-Allow-Origin'] = '*'
      data = json.dumps([revision.AsDict() for revision in revisions])
      self.response.out.write(data)
      return

    page_value = {'revisions': revisions}
    template_values = self.InitializeTemplate('Chromium Revisions Status')
    template_values.update(page_value)
    self.DisplayTemplate('revisions.html', template_values)

  @utils.admin_only
  def post(self):
    """Adds a new revision status."""
    revision = self.request.get('revision')
    success = self.request.get('success')
    steps = self.request.get('steps')
    git_hash = self.request.get('git_hash')
    if revision and success:
      revision = int(revision)
      obj = Revision.all().filter('revision', revision).get()
      if not obj:
        obj = Revision(revision=revision, status=(success=="1"))

      obj.status = (success == "1")
      obj.failed_steps = steps
      if git_hash:
        obj.git_hash = git_hash
        obj.git_hash_set = True

      obj.put()


class LastKnownGoodRevisionSVN(BasePage):
  """Displays the /lkgr and /svn-lkgr pages."""

  def get(self):
    """Look for the latest successful revision and return it."""
    self.response.headers['Cache-Control'] =  'no-cache, private, max-age=5'
    self.response.headers['Content-Type'] = 'text/plain'
    revision = Revision.all().filter('status', True).order('-revision').get()
    if revision:
      self.response.out.write(revision.revision)


class LastKnownGoodRevisionGIT(BasePage):
  """Displays the /git-lkgr page."""

  def get(self):
    """Look for the latest successful revision and return it."""
    self.response.headers['Cache-Control'] =  'no-cache, private, max-age=5'
    self.response.headers['Content-Type'] = 'text/plain'
    revision = (
        Revision.all().filter('status', True).filter('git_hash_set', True)
        .order('-revision').get() )
    if revision:
      self.response.out.write(revision.git_hash)
    else:
      logging.error('OMG There\'s no git-lkgr!?')
      self.abort(404)


def bootstrap():
  if db.GqlQuery('SELECT __key__ FROM Revision').get() is None:
    Revision(revision=0, status=False).put()
