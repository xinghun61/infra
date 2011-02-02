# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""LKGR management webpages."""

from google.appengine.ext import db

from base_page import BasePage


class Revision(db.Model):
  """Description for the revisions table."""
  # The revision for which we save a status.
  revision = db.IntegerProperty(required=True)
  # The date when the revision status got added.
  date = db.DateTimeProperty(auto_now_add=True)
  # The success (True)/Failure (False) status of this revision.
  status = db.BooleanProperty(required=True)
  # The steps that caused the failure (if any).
  failed_steps = db.TextProperty()


class Revisions(BasePage):
  """Displays the revisions page containing the last 100 revisions."""

  def get(self):
    """Sets the information to be displayed on the revisions page."""
    (validated, is_admin) = self.ValidateUser()
    if not validated:
      return

    revisions = Revision.gql('ORDER BY revision DESC LIMIT 100')
    page_value = {'revisions': revisions}
    template_values = self.InitializeTemplate('Chromium Revisions Status')
    template_values.update(page_value)
    self.DisplayTemplate('revisions.html', template_values)

  def post(self):
    """Adds a new revision status."""
    # Get the posted information.
    (validated, is_admin) = self.ValidateUser()
    if not validated:
      return
    revision = self.request.get('revision')
    success = self.request.get('success')
    steps = self.request.get('steps')
    if revision and success:
      revision = Revision(revision=int(revision),
                          status=(success == "1"),
                          failed_steps=steps)
      revision.put()


class LastKnownGoodRevision(BasePage):
  """Displays the /lkgr page."""

  def get(self):
    """Look for the latest successful revision and return it."""
    self.response.headers['Cache-Control'] =  'no-cache, private, max-age=5'
    self.response.headers['Content-Type'] = 'text/plain'
    revision = Revision.gql(
        'WHERE status = :1 ORDER BY revision DESC', True).get()
    if revision:
      self.response.out.write(revision.revision)
