# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Task queue endpoints for creating and updating issues on issue tracker."""

import datetime
import httplib
import json
import logging
import os
import sys
import urllib2
import webapp2

sys.path.insert(0, os.path.join(
  os.path.dirname(os.path.dirname(__file__)), 'third_party'))

from google.appengine.api import app_identity
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.ext import ndb

import apiclient.errors
from findit import findit
import gae_ts_mon
from issue_tracker import issue_tracker_api, issue
from model.flake import (
    Flake, FlakeOccurrence, FlakeUpdate, FlakeUpdateSingleton, FlakyRun)
from model.build_run import BuildRun
from status import build_result, util
from test_results.util import normalize_test_type, flatten_tests_trie


MAX_UPDATED_ISSUES_PER_DAY = 10
MAX_TIME_DIFFERENCE_SECONDS = 12 * 60 * 60
MIN_REQUIRED_FLAKY_RUNS = 3
DAYS_TILL_STALE = 30
DAYS_TO_REOPEN_ISSUE = 3
MAX_INDIVIDUAL_FLAKES_PER_STEP = 50
FLAKY_RUNS_TEMPLATE = (
    'Detected %(new_flakes_count)d new flakes for test/step "%(name)s". To see '
    'the actual flakes, please visit %(flakes_url)s. This message was posted '
    'automatically by the chromium-try-flakes app.%(suffix)s')
RETURN_TO_QUEUE_SUFFIX = (
    'Since flakiness is ongoing, the issue was moved back into %s (unless '
    'already there).')
SUMMARY_TEMPLATE = '"%(name)s" is flaky'
DESCRIPTION_TEMPLATE = (
    '%(summary)s.\n\n'
    'This issue was created automatically by the chromium-try-flakes app. '
    'Please find the right owner to fix the respective test/step and assign '
    'this issue to them. %(other_queue_msg)s\n\n'
    'We have detected %(flakes_count)d recent flakes. List of all flakes can '
    'be found at %(flakes_url)s.\n\n'
    '%(footer)s')
DESCRIPTION_TEST_FOOTER = (
    'Flaky tests should be disabled within 30 minutes unless culprit CL is '
    'found and reverted. Please see more details here: '
    'https://sites.google.com/a/chromium.org/dev/developers/tree-sheriffs/'
    'sheriffing-bug-queues#triaging-auto-filed-flakiness-bugs')
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
TEST_RESULTS_URL_TEMPLATE = (
    'https://test-results.appspot.com/testfile?builder=%(buildername)s&name='
    'full_results.json&master=%(mastername)s&testtype=%(stepname)s&buildnumber='
    '%(buildnumber)s')
NUM_DAYS_IGNORED_IN_QUEUE_FOR_STALENESS = 7
VERY_STALE_FLAKES_MESSAGE_IGNORED = (
    'Reporting to stale-flakes-reports@google.com to investigate why this '
    'issue is not being processed despite being in an appropriate queue for %d '
    'days or more.' % NUM_DAYS_IGNORED_IN_QUEUE_FOR_STALENESS)
NUM_TIMES_IN_QUEUE_FOR_STALENESS = 5
VERY_STALE_FLAKES_MESSAGE_MANY_TIMES = (
    'Reporting to stale-flakes-reports@google.com to investigate why this '
    'issue has been in the appropriate queue %d times or more.' %
    NUM_TIMES_IN_QUEUE_FOR_STALENESS)
STALE_FLAKES_ML = 'stale-flakes-reports@google.com'
MAX_GAP_FOR_FLAKINESS_PERIOD = datetime.timedelta(days=3)
KNOWN_TROOPER_FLAKE_NAMES = [
    'analyze', 'bot_update', 'compile (with patch)', 'compile',
    'device_status_check', 'gclient (with patch)', 'Patch',
    'process_dumps', 'provision_devices', 'update_scripts', 'taskkill',
    'commit-git-patch']

# Flakes in these steps are always ignored:
#  - steps: always red when any other step is red (duplicates failure)
#  - presubmit: typically red due to missing OWNERs LGTM, not a flake
#  - recipe failure reason: always red when build fails (not a failure)
#  - test results: always red when another step is red (not a failure)
#  - Uncaught Exception: summary step referring to an exception in another
#    step (duplicates failure)
#  - Failure reason: similar to 'recipe failure reason'
# There are additional rules for non-trivial cases in the FlakyRun.post method.
IGNORED_STEPS = ['steps', 'presubmit', 'recipe failure reason', 'test results',
                 'Uncaught Exception', 'Failure reason']


def is_trooper_flake(flake_name):
  return flake_name in KNOWN_TROOPER_FLAKE_NAMES


def get_queue_details(flake_name):
  if is_trooper_flake(flake_name):
    return 'Trooper Bug Queue', 'Infra-Troopers'
  else:
    return 'Sheriff Bug Queue', 'Sheriff-Chromium'


class ProcessIssue(webapp2.RequestHandler):
  time_since_first_flake = gae_ts_mon.FloatMetric(
      'flakiness_pipeline/time_since_first_flake',
      'The delay in seconds from the moment first flake occurrence in this '
      'flakiness period happens and until the time an issue is created to '
      'track it.',
      None)
  time_since_threshold_exceeded = gae_ts_mon.FloatMetric(
      'flakiness_pipeline/time_since_threshold_exceeded',
      'The delay in seconds from the moment when the last flake occurrence '
      'happens that makes a flake exceed the threshold and until the time an '
      'issue is created to track it.',
      None)
  issue_updates = gae_ts_mon.CounterMetric(
      'flakiness_pipeline/issue_updates',
      'Issues updated/created',
      [gae_ts_mon.StringField('operation')])

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
    flaky_runs = [run for run in flaky_runs if run is not None]
    return [
      flaky_run for flaky_run in flaky_runs
      if self._is_same_day(flaky_run) and
         self._time_difference(flaky_run) <= MAX_TIME_DIFFERENCE_SECONDS]

  @staticmethod
  @ndb.non_transactional
  def _find_flakiness_period_occurrences(flake):
    """Finds all occurrences in the current flakiness period."""
    assert flake.occurrences, 'Flake entity has no occurrences'
    flaky_runs = sorted([run for run in ndb.get_multi(flake.occurrences)
                             if run is not None],
                        key=lambda run: run.failure_run_time_finished)

    cur = flaky_runs[-1]
    for i, prev in enumerate(reversed(flaky_runs[:-1])):
      if (cur.failure_run_time_finished - prev.failure_run_time_finished >
          MAX_GAP_FOR_FLAKINESS_PERIOD):
        return flaky_runs[-i-1:]  # not including prev, but including cur
      cur = prev
    return flaky_runs

  @staticmethod
  def _get_time_threshold_exceeded(flakiness_period_occurrences):
    assert flakiness_period_occurrences, 'No occurrences in flakiness period'
    window = []
    for flaky_run in flakiness_period_occurrences:  # pragma: no cover
      window.append(flaky_run)

      # Remove flaky runs that happened more than a day before the latest run.
      flaky_run_finished = flaky_run.failure_run_time_finished
      window = [
          prev_run for prev_run in window
          if flaky_run_finished - prev_run.failure_run_time_finished <=
             datetime.timedelta(days=1)
      ]

      if len(window) >= MIN_REQUIRED_FLAKY_RUNS:
        return flaky_run.failure_run_time_finished

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

  @staticmethod
  @ndb.non_transactional
  def _report_flakes_to_findit(flake, flaky_runs):
    try:
      findit.FindItAPI().flake(flake, flaky_runs)
    except (httplib.HTTPException, apiclient.errors.Error):
      logging.warning('Failed to send flakes to FindIt', exc_info=True)

  @staticmethod
  def follow_duplication_chain(api, starting_issue_id):
    """Finds last merged-into issue in the deduplication chain.

    Args:
      api: Issue Tracker API object.
      starting_issue_id: ID of the issue to start with.

    Returns:
      Issue object for the last issue in the chain (can be the same issue as
      passed in if it is not marked as Duplicate) or None if duplication loop is
      detected.
    """
    seen_issues = set()
    flake_issue = api.getIssue(starting_issue_id)
    # We need to check both status and merged_into, since it's possible to
    # create an issue with Duplicate status but without merged_into field set
    # and vice versa (see http://crbug.com/669054 and http://crbug.com/669056).
    while flake_issue.status == 'Duplicate' and flake_issue.merged_into:
      seen_issues.add(flake_issue.id)
      if flake_issue.merged_into in seen_issues:
        logging.info('Detected issue duplication loop: %s.', seen_issues)
        return None
      flake_issue = api.getIssue(flake_issue.merged_into)

    return flake_issue

  @ndb.transactional
  def _update_issue(self, api, flake, new_flakes, now):
    """Updates an issue on the issue tracker."""
    flake_issue = self.follow_duplication_chain(api, flake.issue_id)

    if flake_issue is None:
      # If the issue duplication loop was detected, we re-create the issue.
      self._recreate_issue_for_flake(flake)
      return

    if flake_issue.id != flake.issue_id:
      # Update the issue ID stored in datastore to avoid following deduplication
      # chain next time.
      flake.issue_id = flake_issue.id

    if not flake_issue.open:
      # If the issue was closed, we do not update it. This allows changes made
      # to reduce flakiness to propagate and take effect. If after
      # DAYS_TO_REOPEN_ISSUE days we still detect flakiness, we will create a
      # new issue.
      recent_cutoff = now - datetime.timedelta(days=DAYS_TO_REOPEN_ISSUE)
      if flake_issue.updated < recent_cutoff:
        self._recreate_issue_for_flake(flake)
      return

    # Make sure issue is in the appropriate bug queue as flakiness is ongoing as
    # the sheriffs are supposed to disable flaky tests. For steps, only return
    # if there is no owner on the bug.
    suffix = None
    queue_name, expected_label = get_queue_details(flake.name)
    if expected_label not in flake_issue.labels:
      if not flake.is_step or not flake_issue.owner:
        flake_issue.labels.append(expected_label)
        suffix = RETURN_TO_QUEUE_SUFFIX % queue_name

    new_flaky_runs_msg = FLAKY_RUNS_TEMPLATE % {
        'name': flake.name,
        'new_flakes_count': len(new_flakes),
        'flakes_url': FLAKES_URL_TEMPLATE % flake.key.urlsafe(),
        'suffix': ' %s' % suffix if suffix else ''}
    api.update(flake_issue, comment=new_flaky_runs_msg)
    self.issue_updates.increment_by(1, {'operation': 'update'})
    logging.info('Updated issue %d for flake %s with %d flake runs',
                 flake.issue_id, flake.name, len(new_flakes))
    self._update_new_occurrences_with_issue_id(
        flake.name, new_flakes, flake_issue.id)
    flake.num_reported_flaky_runs = len(flake.occurrences)
    flake.issue_last_updated = now

    self._report_flakes_to_findit(flake, new_flakes)

  @ndb.transactional
  def _create_issue(self, api, flake, new_flakes, now):
    _, qlabel = get_queue_details(flake.name)
    labels = ['Type-Bug', 'Pri-1', 'Via-TryFlakes', qlabel]
    if is_trooper_flake(flake.name):
      other_queue_msg = TROOPER_QUEUE_MSG
    else:
      other_queue_msg = SHERIFF_QUEUE_MSG

    summary = SUMMARY_TEMPLATE % {'name': flake.name}
    description = DESCRIPTION_TEMPLATE % {
        'summary': summary,
        'flakes_url': FLAKES_URL_TEMPLATE % flake.key.urlsafe(),
        'flakes_count': len(new_flakes),
        'other_queue_msg': other_queue_msg,
        'footer': '' if flake.is_step else DESCRIPTION_TEST_FOOTER}
    if flake.old_issue_id:
      description = REOPENED_DESCRIPTION_TEMPLATE % {
          'description': description, 'old_issue': flake.old_issue_id}

    new_issue = issue.Issue({'summary': summary,
                             'description': description,
                             'status': 'Untriaged',
                             'labels': labels,
                             'components': ['Tests>Flaky']})
    flake_issue = api.create(new_issue)
    flake.issue_id = flake_issue.id
    self._update_new_occurrences_with_issue_id(
        flake.name, new_flakes, flake_issue.id)
    flake.num_reported_flaky_runs = len(flake.occurrences)
    flake.issue_last_updated = now
    self.issue_updates.increment_by(1, {'operation': 'create'})
    logging.info('Created a new issue %d for flake %s', flake.issue_id,
                 flake.name)

    self._report_flakes_to_findit(flake, new_flakes)

    # Find all flakes in the current flakiness period to compute metrics. The
    # flakiness period is a series of flakes with a gap no larger than
    # MAX_GAP_FOR_FLAKINESS_PERIOD seconds.
    period_flakes = self._find_flakiness_period_occurrences(flake)

    # Compute the delay since the first flake in the current flakiness period.
    time_since_first_flake = (
        now - period_flakes[0].failure_run_time_finished).total_seconds()
    self.time_since_first_flake.set(time_since_first_flake)
    logging.info('Reported time_since_first_flake %d for flake %s',
                 time_since_first_flake, flake.name)

    # Find the first flake that exceeded the threshold needed to create an
    # issue and report delay from the moment this flake happend and until we've
    # actually created the issue.
    time_since_threshold_exceeded = (
        now - self._get_time_threshold_exceeded(period_flakes)).total_seconds()
    self.time_since_threshold_exceeded.set(time_since_threshold_exceeded)
    logging.info('Reported time_since_threshold_exceeded %d for flake %s',
                 time_since_threshold_exceeded, flake.name)


  @ndb.transactional(xg=True)  # pylint: disable=E1120
  def post(self, urlsafe_key):
    api = issue_tracker_api.IssueTrackerAPI('chromium')

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

  def _update_all_flakes_with_new_issue_id(self, old_issue_id, new_issue_id):
    for flake in Flake.query(Flake.issue_id == old_issue_id):
      logging.info(
          'Updating issue_id from %s to %s', old_issue_id, new_issue_id)
      flake.issue_id = new_issue_id
      flake.put()

  def post(self, issue_id):
    """Check if an issue is stale and report it back to appropriate queue.

    Check if the issue is stale, i.e. has not been updated by anyone else than
    this app in the last DAYS_TILL_STALE days, and if this is the case, then
    move it back to the appropriate queue. Also if the issue is stale for
    NUM_DAYS_IGNORED_IN_QUEUE_FOR_STALENESS days, report it to
    stale-flakes-reports@google.com to investigate why it is not being processed
    despite being in the appropriate queue.
    """
    issue_id = int(issue_id)
    api = issue_tracker_api.IssueTrackerAPI('chromium')
    flake_issue = ProcessIssue.follow_duplication_chain(api, issue_id)
    now = datetime.datetime.utcnow()

    if not flake_issue:
      # If we've detected deduplication loop, then just remove issue from all
      # affected flakes and ignore it.
      self._remove_issue_from_flakes(issue_id)
      return

    if not flake_issue.open:
      # Remove issue_id from all flakes unless it has recently been updated. We
      # should not remove issue_id too soon, otherwise issues will get reopened
      # before changes made will propogate and reduce flakiness.
      recent_cutoff = now - datetime.timedelta(days=DAYS_TO_REOPEN_ISSUE)
      if flake_issue.updated < recent_cutoff:
        self._remove_issue_from_flakes(issue_id)
      return

    if flake_issue.id != issue_id:
      self._update_all_flakes_with_new_issue_id(issue_id, flake_issue.id)
      issue_id = flake_issue.id

    # Parse the flake name from the first comment (which we post ourselves).
    comments = sorted(api.getComments(issue_id), key=lambda c: c.created)
    original_summary = comments[0].comment.splitlines()[0]
    flake_name = original_summary[len('"'):-len('" is flaky')]
    _, expected_label = get_queue_details(flake_name)

    # Report to stale-flakes-reports@ if the issue has been in appropriate queue
    # without any updates for NUM_DAYS_IGNORED_IN_QUEUE_FOR_STALENESS days.
    stale_deadline = now - datetime.timedelta(
        days=NUM_DAYS_IGNORED_IN_QUEUE_FOR_STALENESS)
    last_updated = comments[-1].created
    if (last_updated < stale_deadline and
        expected_label in flake_issue.labels and
        STALE_FLAKES_ML not in flake_issue.cc):
      flake_issue.cc.append(STALE_FLAKES_ML)
      logging.info('Reporting issue %s to %s', flake_issue.id, STALE_FLAKES_ML)
      api.update(flake_issue, comment=VERY_STALE_FLAKES_MESSAGE_IGNORED)

    # Report to stale-flake-reports@ if the issue has been in the appropriate
    # queue more than NUM_TIMES_IN_QUEUE_FOR_STALENESS times.
    num_times_in_queue = 0
    for comment in comments:
      if expected_label in comment.labels:
        num_times_in_queue += 1
      # After the issue is investigated, the manager of the stale mailing list
      # will remove the list from CC and the issue should not be returned back
      # to the list unless it is returned to appropriate queue more than
      # NUM_TIMES_IN_QUEUE_FOR_STALENESS times again. Therefore, once we see a
      # comment that removes the stale mailing list, we reset the counter.
      remove_stale_flake_ml = '-%s' % STALE_FLAKES_ML
      if remove_stale_flake_ml in comment.cc:
        num_times_in_queue = 0
    if (num_times_in_queue >= NUM_TIMES_IN_QUEUE_FOR_STALENESS and
        STALE_FLAKES_ML not in flake_issue.cc):
      flake_issue.cc.append(STALE_FLAKES_ML)
      logging.info('Reporting issue %s to %s', flake_issue.id, STALE_FLAKES_ML)
      api.update(flake_issue, comment=VERY_STALE_FLAKES_MESSAGE_MANY_TIMES)


class CreateFlakyRun(webapp2.RequestHandler):
  flaky_runs = gae_ts_mon.CounterMetric(
      'flakiness_pipeline/flake_occurrences_recorded',
      'Recorded flake occurrences.',
      None)

  # We execute below method in an indepedent transaction since otherwise we
  # would exceed the maximum number of entities allowed within a single
  # transaction.
  @staticmethod
  # pylint: disable=E1120
  @ndb.transactional(xg=True, propagation=ndb.TransactionOptions.INDEPENDENT)
  def add_failure_to_flake(name, flaky_run_key, failure_time, is_step):
    flake = Flake.get_by_id(name)
    if not flake:
      flake = Flake(name=name, id=name, last_time_seen=datetime.datetime.min,
                    is_step=is_step)
      flake.put()

    flake.occurrences.append(flaky_run_key)
    # TODO(sergiyb): This is necessary to update existing flakes. Remove in July
    # 2016 or later.
    flake.is_step = is_step
    util.add_occurrence_time_to_flake(flake, failure_time)
    flake.put()

  @classmethod
  def _flatten_tests(cls, tests, delimiter):
    """Finds all passed, failed and skipped tests in tests trie.

    Test names are produced by concatenating parent node names with delimieter.

    We only return 3 types of tests:
     - passed, i.e. expected is "PASS" and last actual run is "PASS"
     - failed, i.e. expected is "PASS" and last actual run is "FAIL", "TIMEOUT"
       or "CRASH"
     - skipped, i.e. expected and actual are both "SKIP"

    We do not classify or return any other tests, in particular:
     - known flaky, i.e. expected to have varying results, e.g. "PASS FAIL".
     - known failing, i.e. expected is "FAIL", "TIMEOUT" or "CRASH".
     - unexpected flakiness, i.e. failures than hapeneed before last PASS.

    Args:
      delimiter: Delimiter to use for concatenating parts of test name.
      tests: Any non-leaf node of the hierarchical GTest JSON test structure.

    Returns:
      A tuple (passed, failed, skpped), where each is a list of test names.
    """
    passed = []
    failed = []
    skipped = []
    for name, test in flatten_tests_trie(tests, delimiter).iteritems():
      if test['expected'] == ['PASS']:
        last_result = test['actual'][-1]
        if last_result == 'PASS':
          passed.append(name)
        elif last_result in ('FAIL', 'TIMEOUT', 'CRASH'):
          failed.append(name)
      elif test['expected'] == ['SKIP'] and test['actual'] == ['SKIP']:
        skipped.append(name)

    return passed, failed, skipped

  # see examples:
  # compile https://build.chromium.org/p/tryserver.chromium.mac/json/builders/
  #         mac_chromium_compile_dbg/builds/11167?as_text=1
  # gtest https://build.chromium.org/p/tryserver.chromium.win/json/builders/
  #       win_chromium_x64_rel_swarming/builds/4357?as_text=1
  # TODO(jam): get specific problem with compile so we can use that as name
  @classmethod
  def get_flakes(cls, mastername, buildername, buildnumber, step):
    """Returns a list of flakes in a given step.

    It can either be entire step or a list of specific tests.

    Args:
      mastername: Master name on which step has been run.
      buildername: Builder name on which step has been run.
      buildnume: Number of the build in which step has been run.
      step: Step name.

    Returns:
      (flakes, is_step), where flakes is a list of flake names and is_step is
      True when the whole step is a flake, in which case flakes is a list
      containing a single entry - the name of the step.
    """
    # If test results were invalid, report whole step as flaky.
    steptext = ' '.join(step['text'])
    stepname = normalize_test_type(step['name'])
    if 'TEST RESULTS WERE INVALID' in steptext:
      return [stepname], True

    url = TEST_RESULTS_URL_TEMPLATE % {
      'mastername': urllib2.quote(mastername),
      'buildername': urllib2.quote(buildername),
      'buildnumber': urllib2.quote(str(buildnumber)),
      'stepname': urllib2.quote(stepname),
    }

    try:
      result = urlfetch.fetch(url)

      if result.status_code >= 200 and result.status_code < 400:
        json_result = json.loads(result.content)

        _, failed, _ = cls._flatten_tests(
            json_result.get('tests', {}),
            json_result.get('path_delimiter', '/'))
        if len(failed) > MAX_INDIVIDUAL_FLAKES_PER_STEP:
          return [stepname], True
        return failed, False

      if result.status_code == 404:
        # This is quite a common case (only some failing steps are actually
        # running tests and reporting results to flakiness dashboard).
        logging.info('Failed to retrieve JSON from %s', url)
      else:
        logging.exception('Failed to retrieve JSON from %s', url)
    except Exception:
      logging.exception('Failed to retrieve or parse JSON from %s', url)

    return [stepname], True

  @ndb.transactional(xg=True)  # pylint: disable=E1120
  def post(self):
    if (not self.request.get('failure_run_key') or
        not self.request.get('success_run_key')):
      self.response.set_status(400, 'Invalid request parameters')
      return

    failure_run = ndb.Key(urlsafe=self.request.get('failure_run_key')).get()
    success_run = ndb.Key(urlsafe=self.request.get('success_run_key')).get()

    flaky_run = FlakyRun(
        failure_run=failure_run.key,
        failure_run_time_started=failure_run.time_started,
        failure_run_time_finished=failure_run.time_finished,
        success_run=success_run.key)

    failure_time = failure_run.time_finished
    patchset_builder_runs = failure_run.key.parent().get()

    # TODO(sergiyb): The parsing logic below is very fragile and will break with
    # any changes to step names and step text. We should move away from parsing
    # buildbot to tools like flakiness dashboard (test-results.appspot.com),
    # which uses a standartized JSON format.
    master = BuildRun.removeMasterPrefix(patchset_builder_runs.master)
    url = ('https://build.chromium.org/p/' + master +
           '/json/builders/' + patchset_builder_runs.builder +'/builds/' +
           str(failure_run.buildnumber))
    urlfetch.set_default_fetch_deadline(60)
    logging.info('get_flaky_run_reason ' + url)
    response = urlfetch.fetch(url)
    if response.status_code == 404:
      logging.warning(
          'The build request %s has returned 404, which likely means it has '
          'expired and can not be retrieved anymore.', url)
      return
    json_result = json.loads(response.content)
    steps = json_result['steps']

    failed_steps = []
    passed_steps = []
    for step in steps:
      result = step['results'][0]
      if build_result.isResultSuccess(result):
        passed_steps.append(step)
        continue
      if not build_result.isResultFailure(result):
        continue
      step_name = step['name']
      step_text = ' '.join(step['text'])
      if step_name in IGNORED_STEPS:
        continue

      # Custom (non-trivial) rules for ignoring flakes in certain steps:
      #  - [swarming] ...: summary step would also be red (do not double count)
      #  - Patch failure: ingore non-infra failures as they are typically due to
      #    changes in the code on HEAD
      #  - bot_update PATCH FAILED: Duplicates failure in 'Patch failure' step.
      #  - ... (retry summary): this is an artificial step to fail the build due
      #    to another step that has failed earlier (do not double count).
      if (step_name.startswith('[swarming]') or
          (step_name == 'Patch failure' and result != build_result.EXCEPTION) or
          (step_name == 'bot_update' and 'PATCH FAILED' in step_text)):
        continue

      failed_steps.append(step)

    steps_to_ignore = []
    for step in failed_steps:
      step_name = step['name']
      if '(with patch)' in step_name:
        # Ignore any steps from the same test suite, which is determined by the
        # normalized step name. Additionally, if the step fails without patch,
        # ignore the original step as well because tree is busted.
        normalized_step_name = normalize_test_type(step_name, True)
        for other_step in failed_steps:
          if other_step == step:
            continue
          normalized_other_step_name = normalize_test_type(
              other_step['name'], True)
          if normalized_other_step_name == normalized_step_name:
            steps_to_ignore.append(other_step['name'])
            if '(without patch)' in other_step['name']:
              steps_to_ignore.append(step['name'])

    flakes_to_update = []
    for step in failed_steps:
      step_name = step['name']
      if step_name in steps_to_ignore:
        continue
      flakes, is_step = self.get_flakes(
          master, patchset_builder_runs.builder, failure_run.buildnumber, step)
      for flake in flakes:
        flake_occurrence = FlakeOccurrence(name=step_name, failure=flake)
        flaky_run.flakes.append(flake_occurrence)
        flakes_to_update.append((flake, is_step))

    # Do not create FlakyRuns if all failed steps have been ignored.
    if not flaky_run.flakes:
      return

    flaky_run_key = flaky_run.put()
    for flake, is_step in flakes_to_update:
      self.add_failure_to_flake(flake, flaky_run_key, failure_time, is_step)
    self.flaky_runs.increment_by(1)


class OverrideIssueId(webapp2.RequestHandler):
  def get(self):
    # 'login: required' in app.yaml guarantees that we'll get a valid user here
    user_email = users.get_current_user().email()
    if not user_email.endswith('@chromium.org'):
      self.response.set_status(401)
      self.response.write(
          'Please login with your chromium.org account. <a href="%s">Logout'
          '</a>.' % users.create_logout_url(self.request.url))
      return

    try:
      issue_id = int(self.request.get('issue_id'))
    except (TypeError, ValueError) as e:
      self.response.set_status(400)
      self.response.write('Failed to parse Issue ID as an integer.')
      return

    if issue_id < 0:
      self.response.set_status(400)
      self.response.write('Issue ID must be positive or 0.')
      return

    if issue_id != 0:
      api = issue_tracker_api.IssueTrackerAPI('chromium')
      try:
        api.getIssue(issue_id)
      except apiclient.errors.HttpError as e:
        if e.resp.status != 404:
          raise
        self.response.set_status(404)
        self.response.write(
            'Failed to find issue %d on issue tracker: %s.' % (issue_id, e))
        return

    key = self.request.get('key')
    flake = ndb.Key(urlsafe=key).get()
    flake.issue_id = issue_id
    flake.put()

    logging.info('%s updated issue_id for flake %s to %d.', user_email,
                 flake.name, issue_id)
    self.redirect('/all_flake_occurrences?key=%s' % key)
