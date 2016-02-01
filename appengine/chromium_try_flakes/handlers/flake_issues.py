# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Task queue endpoints for creating and updating issues on issue tracker."""

import datetime
import logging
import webapp2

from google.appengine.api import app_identity
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from issue_tracker import issue_tracker_api, issue
from model.flake import FlakeUpdateSingleton, FlakeUpdate, Flake
from infra_libs import ts_mon


MAX_UPDATED_ISSUES_PER_DAY = 50
MAX_TIME_DIFFERENCE_SECONDS = 12 * 60 * 60
MIN_REQUIRED_FLAKY_RUNS = 5
DAYS_TILL_STALE = 3
USE_MONORAIL = False
DAYS_TO_REOPEN_ISSUE = 3
FLAKY_RUNS_TEMPLATE = (
    'Detected %(new_flakes_count)d new flakes for test/step "%(name)s". To see '
    'the actual flakes, please visit %(flakes_url)s. This message was posted '
    'automatically by the chromium-try-flakes app.')
SUMMARY_TEMPLATE = '"%(name)s" is flaky'
DESCRIPTION_TEMPLATE = (
    '%(summary)s.\n\n'
    'This issue was created automatically by the chromium-try-flakes app. '
    'Please find the right owner to fix the respective test/step and assign '
    'this issue to them. %(other_queue_msg)s\n\n'
    'We have detected %(flakes_count)d recent flakes. List of all flakes can '
    'be found at %(flakes_url)s.')
SHERIFF_QUEUE_MSG = (
    'If the step/test is infrastructure-related, please add Infra-Troopers '
    'label and change issue status to Untriaged. When done, please remove the '
    'issue from Sheriff Bug Queue by removing the Sheriff-Chromium label.')
TROOPER_QUEUE_MSG = (
    'If the step/test is not infrastructure-related (e.g. flaky test), please '
    'add Sheriff-Chromium label and change issue status to Untriaged. When '
    'done, please remove the issue from Trooper Bug Queue by removing the '
    'Infra-Troopers label.')
REOPENED_DESCRIPTION_TEMPLATE = (
    '%(description)s\n\n'
    'This flaky test/step was previously tracked in issue %(old_issue)d.')
FLAKES_URL_TEMPLATE = (
    'https://chromium-try-flakes.appspot.com/all_flake_occurrences?key=%s')
BACK_TO_SHERIFF_MESSAGE = (
    'There has been no update on this issue for over %d days, therefore it has '
    'been moved back into the Sheriff queue (unless it was already there). '
    'Sheriffs, please make sure that owner is aware of the issue and assign to '
    'another owner if necessary. If the flaky test/step has already been '
    'fixed, please close this issue.' % DAYS_TILL_STALE)
VERY_STALE_FLAKES_MESSAGE = (
    'Reporting to stale-flakes-reports@google.com to investigate why this '
    'issue is not being processed by Sheriffs.')
STALE_FLAKES_ML = 'stale-flakes-reports@google.com'
MAX_GAP_FOR_FLAKINESS_PERIOD = datetime.timedelta(days=3)
KNOWN_TROOPER_FAILURES = [
    'compile (with patch)', 'gclient runhooks (with patch)', 'analyze',
    'device_status_check', 'Patch failure', 'process_dumps']



class ProcessIssue(webapp2.RequestHandler):
  reporting_delay = ts_mon.FloatMetric(
      'flakiness_pipeline/reporting_delay',
      description='The delay in seconds from the moment first flake occurrence '
                  'in this flakiness period happens and until the time an '
                  'issue is created to track it.')

  @ndb.transactional
  def _get_flake_update_singleton_key(self):
    singleton_key = ndb.Key('FlakeUpdateSingleton', 'singleton')
    if not singleton_key.get():
      FlakeUpdateSingleton(key=singleton_key).put()
    return singleton_key

  @ndb.transactional
  def _increment_update_counter(self):
    FlakeUpdate(parent=self._get_flake_update_singleton_key()).put()

  @ndb.non_transactional
  def _time_difference(self, flaky_run):
    return (flaky_run.success_run.get().time_finished -
            flaky_run.failure_run_time_finished).total_seconds()

  @ndb.non_transactional
  def _is_same_day(self, flaky_run):
    time_since_finishing = (
        datetime.datetime.utcnow() - flaky_run.failure_run_time_finished)
    return time_since_finishing <= datetime.timedelta(days=1)

  @ndb.non_transactional
  def _get_new_flakes(self, flake):
    num_runs = len(flake.occurrences) - flake.num_reported_flaky_runs
    flaky_runs = ndb.get_multi(flake.occurrences[-num_runs:])
    return [
      flaky_run for flaky_run in flaky_runs
      if self._is_same_day(flaky_run) and
         self._time_difference(flaky_run) <= MAX_TIME_DIFFERENCE_SECONDS]

  @staticmethod
  @ndb.non_transactional
  def _get_first_flake_occurrence_time(flake):
    assert flake.occurrences, 'Flake entity has no occurrences'
    rev_occ = sorted(flake.occurrences, reverse=True)
    last_occ_time = rev_occ[0].get().failure_run_time_finished
    for occ in rev_occ[1:]:
      occ_time = occ.get().failure_run_time_finished
      if last_occ_time - occ_time > MAX_GAP_FOR_FLAKINESS_PERIOD:
        break
      last_occ_time = occ_time
    return last_occ_time

  @ndb.transactional
  def _recreate_issue_for_flake(self, flake):
    """Updates a flake to re-create an issue and creates a respective task."""
    flake.old_issue_id = flake.issue_id
    flake.issue_id = 0
    taskqueue.add(url='/issues/process/%s' % flake.key.urlsafe(),
                  queue_name='issue-updates', transactional=True)

  @staticmethod
  @ndb.non_transactional
  def _update_new_occurrences_with_issue_id(name, new_flaky_runs, issue_id):
    # TODO(sergiyb): Find a way to do this asynchronously to avoid block
    # transaction-bound method calling this. Possible solutions are to use
    # put_multi_sync (need to find a way to test this) or to use deferred
    # execution.
    for fr in new_flaky_runs:
      for occ in fr.flakes:
        if occ.failure == name:
          occ.issue_id = issue_id
    ndb.put_multi(new_flaky_runs)

  @ndb.transactional
  def _update_issue(self, api, flake, new_flakes, now):
    """Updates an issue on the issue tracker."""
    flake_issue = api.getIssue(flake.issue_id)

    # Handle cases when an issue has been closed. We need to do this in a loop
    # because we might move onto another issue.
    seen_issues = set()
    while not flake_issue.open:
      if flake_issue.status == 'Duplicate':
        # If the issue was marked as duplicate, we update the issue ID stored in
        # datastore to the one it was merged into and continue working with the
        # new issue.
        seen_issues.add(flake_issue.id)
        if flake_issue.merged_into not in seen_issues:
          flake.issue_id = flake_issue.merged_into
          flake_issue = api.getIssue(flake.issue_id)
        else:
          logging.info('Detected issue duplication loop: %s. Re-creating an '
                       'issue for the flake %s.', seen_issues, flake.name)
          self._recreate_issue_for_flake(flake)
          return
      else:  # Fixed, WontFix, Verified, Archived, custom status
        # If the issue was closed, we do not update it. This allows changes made
        # to reduce flakiness to propagate and take effect. If after
        # DAYS_TO_REOPEN_ISSUE days we still detect flakiness, we will create a
        # new issue.
        recent_cutoff = now - datetime.timedelta(days=DAYS_TO_REOPEN_ISSUE)
        if flake_issue.updated < recent_cutoff:
          self._recreate_issue_for_flake(flake)
        return

    new_flaky_runs_msg = FLAKY_RUNS_TEMPLATE % {
        'name': flake.name,
        'new_flakes_count': len(new_flakes),
        'flakes_url': FLAKES_URL_TEMPLATE % flake.key.urlsafe()}
    api.update(flake_issue, comment=new_flaky_runs_msg)
    logging.info('Updated issue %d for flake %s with %d flake runs',
                 flake.issue_id, flake.name, len(new_flakes))
    self._update_new_occurrences_with_issue_id(
        flake.name, new_flakes, flake_issue.id)
    flake.num_reported_flaky_runs = len(flake.occurrences)
    flake.issue_last_updated = now

  def _is_trooper_issue(self, flake):
    return flake.name in KNOWN_TROOPER_FAILURES

  @ndb.transactional
  def _create_issue(self, api, flake, new_flakes, now):
    labels = ['Type-Bug', 'Pri-1', 'Cr-Tests-Flaky', 'Via-TryFlakes']
    if self._is_trooper_issue(flake):
      labels.append('Infra-Troopers')
      other_queue_msg = TROOPER_QUEUE_MSG
    else:
      labels.append('Sheriff-Chromium')
      other_queue_msg = SHERIFF_QUEUE_MSG

    summary = SUMMARY_TEMPLATE % {'name': flake.name}
    description = DESCRIPTION_TEMPLATE % {
        'summary': summary,
        'flakes_url': FLAKES_URL_TEMPLATE % flake.key.urlsafe(),
        'flakes_count': len(new_flakes),
        'other_queue_msg': other_queue_msg}
    if flake.old_issue_id:
      description = REOPENED_DESCRIPTION_TEMPLATE % {
          'description': description, 'old_issue': flake.old_issue_id}

    new_issue = issue.Issue({'summary': summary,
                             'description': description,
                             'status': 'Untriaged',
                             'labels': labels})
    flake_issue = api.create(new_issue)
    flake.issue_id = flake_issue.id
    self._update_new_occurrences_with_issue_id(
        flake.name, new_flakes, flake_issue.id)
    flake.num_reported_flaky_runs = len(flake.occurrences)
    flake.issue_last_updated = now
    logging.info('Created a new issue %d for flake %s', flake.issue_id,
                 flake.name)

    self.reporting_delay.set(
        (now - self._get_first_flake_occurrence_time(flake)).total_seconds())

  @ndb.transactional(xg=True)  # pylint: disable=E1120
  def post(self, urlsafe_key):
    api = issue_tracker_api.IssueTrackerAPI(
        'chromium', use_monorail=USE_MONORAIL)

    # Check if we should stop processing this issue because we've posted too
    # many updates to issue tracker today already.
    day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    num_updates_last_day = FlakeUpdate.query(
        FlakeUpdate.time_updated > day_ago,
        ancestor=self._get_flake_update_singleton_key()).count()
    if num_updates_last_day >= MAX_UPDATED_ISSUES_PER_DAY:
      return

    now = datetime.datetime.utcnow()
    flake = ndb.Key(urlsafe=urlsafe_key).get()
    # Only update/file issues if there are new flaky runs.
    if flake.num_reported_flaky_runs == len(flake.occurrences):
      return

    # Retrieve flaky runs outside of the transaction, because we are not
    # planning to modify them and because there could be more of them than the
    # number of groups supported by cross-group transactions on AppEngine.
    new_flakes = self._get_new_flakes(flake)

    if len(new_flakes) < MIN_REQUIRED_FLAKY_RUNS:
      return

    if flake.issue_id > 0:
      # Update issues at most once a day.
      if flake.issue_last_updated > now - datetime.timedelta(days=1):
        return

      self._update_issue(api, flake, new_flakes, now)
      self._increment_update_counter()
    else:
      self._create_issue(api, flake, new_flakes, now)
      # Don't update the issue just yet, this may fail, and we need the
      # transaction to succeed in order to avoid filing duplicate bugs.
      self._increment_update_counter()

    # Note that if transaction fails for some reason at this point, we may post
    # updates or create issues multiple times. On the other hand, this should be
    # extremely rare because we set the number of concurrently running tasks to
    # 1, therefore there should be no contention for updating this issue's
    # entity.
    flake.put()


class UpdateIfStaleIssue(webapp2.RequestHandler):
  def _remove_issue_from_flakes(self, issue_id):
    for flake in Flake.query(Flake.issue_id == issue_id):
      logging.info('Removing issue_id %s from %s', issue_id, flake.key)
      flake.old_issue_id = issue_id
      flake.issue_id = 0
      flake.put()

  def post(self, issue_id):
    """Check if an issue is stale and report it back to sheriff.

    Check if the issue is stale, i.e. has not been updated by anyone else than
    this app in the last DAYS_TILL_STALE days, and if this is the case, then
    move it back to the Sheriff queue. Also if the issue is stale for 7 days,
    report it to stale-flakes-reports@google.com to investigate why it is not
    being processed by sheriffs.
    """
    issue_id = int(issue_id)
    api = issue_tracker_api.IssueTrackerAPI(
        'chromium', use_monorail=USE_MONORAIL)
    flake_issue = api.getIssue(issue_id)
    now = datetime.datetime.utcnow()

    if not flake_issue.open:
      # Remove issue_id from all flakes unless it has recently been updated. We
      # should not remove issue_id too soon, otherwise issues will get reopened
      # before changes made will propogate and reduce flakiness.
      recent_cutoff = now - datetime.timedelta(days=DAYS_TO_REOPEN_ISSUE)
      if flake_issue.updated < recent_cutoff:
        self._remove_issue_from_flakes(issue_id)
      return

    # Find the last update, which defaults to when issue was created if no third
    # party updates were posted.
    comments = api.getComments(issue_id)
    last_third_party_update = flake_issue.created
    for comment in sorted(comments, key=lambda c: c.created, reverse=True):
      if comment.author != app_identity.get_service_account_name():
        last_third_party_update = comment.created
        break

    # Compute stale deadline (in the past). Issues without updates after it
    # should be considered stale. Only consider weekdays to avoid bringing
    # issues back that were filed shortly before weekend.
    stale_deadline = now - datetime.timedelta(days=DAYS_TILL_STALE)
    if stale_deadline.weekday() > 4:  # on weekend
      stale_deadline -= datetime.timedelta(days=2)

    # Put back into Sheriff Bug Queue if stale and unless already there.
    if (last_third_party_update < stale_deadline and
        'Sheriff-Chromium' not in flake_issue.labels):
      flake_issue.labels.append('Sheriff-Chromium')
      logging.info('Moving issue %s back to Sheriff Bug queue', flake_issue.id)
      api.update(flake_issue, comment=BACK_TO_SHERIFF_MESSAGE)
      return

    # Report to stale-flakes-reports@ if the issue has no updates for 7 days.
    week_ago = now - datetime.timedelta(days=7)
    if (last_third_party_update < week_ago and
        STALE_FLAKES_ML not in flake_issue.cc):
      flake_issue.cc.append(STALE_FLAKES_ML)
      logging.info('Reporting issue %s to %s', flake_issue.id, STALE_FLAKES_ML)
      api.update(flake_issue, comment=VERY_STALE_FLAKES_MESSAGE)
