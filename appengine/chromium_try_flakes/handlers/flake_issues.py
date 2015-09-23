# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Task queue endpoints for creating and updating issues on issue tracker."""

import datetime
import logging
import sha
import webapp2

from google.appengine.api import taskqueue
from google.appengine.ext import ndb


class UpdateIssue(webapp2.RequestHandler):
  @ndb.non_transactional
  def _get_flaky_runs(self, flake):
    return ndb.get_multi(flake.occurrences[flake.num_reported_flaky_runs:])

  @ndb.transactional
  def post(self, urlsafe_key):
    """Updates an issue on the issue tracker."""
    now = datetime.datetime.utcnow()
    flake = ndb.Key(urlsafe=urlsafe_key).get()

    # Update issues at most once an hour.
    if flake.issue_last_updated > now - datetime.timedelta(hours=1):
      return

    # Only update issues if the are new flaky runs.
    if flake.num_reported_flaky_runs == len(flake.occurrences):
      return

    # Retrieve flaky runs outside of the transaction, because we are not
    # planning to modify them and because there could be more of them than the
    # number of groups supported by cross-group transactions on AppEngine.
    new_flaky_runs = self._get_flaky_runs(flake)
    flake.num_reported_flaky_runs = len(flake.occurrences)

    # TODO(sergiyb): Actually update issue.

    logging.info('Updated issue %d for flake %s with %d flake runs',
                 flake.issue_id, flake.name, len(new_flaky_runs))
    flake.issue_last_updated = now

    # Note that if transaction fails for some reason at this point, we may post
    # updates multiple times. On the other hand, this should be extremely rare
    # becase we set the number of concurrently running tasks to 1.
    flake.put()


class CreateIssue(webapp2.RequestHandler):
  @ndb.transactional
  def post(self, urlsafe_key):
    flake = ndb.Key(urlsafe=urlsafe_key).get()

    # TODO(sergiyb): Actually start filing issues.
    flake.issue_id = -1  # fake issue id until we will create issues for real

    logging.info('Created a new issue %d for flake %s', flake.issue_id,
                 flake.name)
    flake.put()

    taskqueue.add(url='/issues/update/%s' % flake.key.urlsafe(),
                  queue_name='issue-updates', transactional=True)


class ProcessIssue(webapp2.RequestHandler):
  @ndb.transactional
  def post(self, urlsafe_key):
    flake = ndb.Key(urlsafe=urlsafe_key).get()

    # TODO(sergiyb): Also consider that issues may be closed as Duplicate,
    # Fixed, Verified, WontFix, Archived - we need to handle these cases
    # appropriately, i.e. file new issues or re-open existing ones.
    if flake.issue_id == 0:
      task_name = 'create_issue_for_%s' % sha.new(flake.name).hexdigest()
      try:
        taskqueue.add(name=task_name, queue_name='issue-updates',
                      url='/issues/create/%s' % flake.key.urlsafe())
      except taskqueue.TombstonedTaskError:
        pass
    else:
      taskqueue.add(url='/issues/update/%s' % flake.key.urlsafe(),
                    queue_name='issue-updates', transactional=True)
