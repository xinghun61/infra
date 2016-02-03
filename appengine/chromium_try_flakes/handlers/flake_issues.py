# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Task queue endpoints for creating and updating issues on issue tracker."""

import datetime
import json
import logging
import webapp2

from google.appengine.api import app_identity
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.ext import ndb

from infra_libs import ts_mon
from issue_tracker import issue_tracker_api, issue
from model.flake import (
    Flake, FlakeOccurrence, FlakeUpdate, FlakeUpdateSingleton, FlakyRun)
from status import build_result, util


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
    'analyze', 'bot_update', 'compile (with patch)', 'compile',
    'device_status_check', 'gclient runhooks (with patch)', 'Patch failure',
    'process_dumps', 'provision_devices', 'update_scripts']


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

    delay = (now - self._get_first_flake_occurrence_time(flake)).total_seconds()
    self.reporting_delay.set(delay)
    logging.info('Reported reporting_delay %d for flake %s', delay, flake.name)

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


class CreateFlakyRun(webapp2.RequestHandler):
  # We execute below method in an indepedent transaction since otherwise we
  # would exceed the maximum number of entities allowed within a single
  # transaction.
  @staticmethod
  # pylint: disable=E1120
  @ndb.transactional(xg=True, propagation=ndb.TransactionOptions.INDEPENDENT)
  def add_failure_to_flake(name, flaky_run_key, failure_time):
    flake = Flake.get_by_id(name)
    if not flake:
      flake = Flake(name=name, id=name, last_time_seen=datetime.datetime.min)
      flake.put()

    flake.occurrences.append(flaky_run_key)
    util.add_occurrence_time_to_flake(flake, failure_time)
    flake.put()

  # see examples:
  # compile http://build.chromium.org/p/tryserver.chromium.mac/json/builders/
  #         mac_chromium_compile_dbg/builds/11167?as_text=1
  # gtest http://build.chromium.org/p/tryserver.chromium.win/json/builders/
  #       win_chromium_x64_rel_swarming/builds/4357?as_text=1
  # TODO(jam): get specific problem with compile so we can use that as name
  # TODO(jam): It's unfortunate to have to parse this html. Can we get it from
  # another place instead of the tryserver's json?
  @staticmethod
  def get_flakes(step):
    combined = ' '.join(step['text'])

    # If test results were invalid, report whole step as flaky.
    if 'TEST RESULTS WERE INVALID' in combined:
      return [combined]

    #gtest
    gtest_search_str = 'failures:<br/>'
    gtest_search_index = combined.find(gtest_search_str)
    if gtest_search_index != -1:
      failures = combined[gtest_search_index + len(gtest_search_str):]
      failures = failures.split('<br/>')
      results = []
      for failure in failures:
        if not failure:
          continue
        if failure == 'ignored:':
          break  # layout test output
        results.append(failure)
      return results

    #gpu
    gpu_search_str = '&tests='
    gpu_search_index = combined.find(gpu_search_str)
    if gpu_search_index != -1:
      failures = combined[gpu_search_index + len(gpu_search_str):]
      end_index = failures.find('">')
      failures = failures[:end_index  ]
      failures = failures.split(',')
      results = []
      for failure in failures:
        if not failure:
          continue
        results.append(failure)
      return results

    return [combined]

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

    success_time = success_run.time_finished
    failure_time = failure_run.time_finished
    patchset_builder_runs = failure_run.key.parent().get()
    url = ('http://build.chromium.org/p/' + patchset_builder_runs.master +
           '/json/builders/' + patchset_builder_runs.builder +'/builds/' +
           str(failure_run.buildnumber))
    urlfetch.set_default_fetch_deadline(60)
    logging.info('get_flaky_run_reason ' + url)
    result = urlfetch.fetch(url).content
    try:
      json_result = json.loads(result)
    except ValueError:
      logging.exception('couldnt decode json for %s', url)
      return
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
      # The following step failures are ignored:
      #  - steps: always red when any other step is red (not a failure)
      #  - [swarming] ...: summary step would also be red (do not double count)
      #  - presubmit: typically red due to missing OWNERs LGTM, not a flake
      #  - recipe failure reason: always red when build fails (not a failure)
      #  - Patch failure: if success run was before failure run, it is
      #    likely a legitimate failure. For example it often happens that
      #    developers use CQ dry run and then wait for a review. Once getting
      #    LGTM they check CQ checkbox, but the patch does not cleanly apply
      #    anymore.
      #  - bot_update PATCH FAILED: Corresponds to 'Patch failure' step.
      #  - test results: always red when another step is red (not a failure)
      #  - Uncaught Exception: summary step referring to an exception in another
      #    step (e.g. bot_update)
      if (step_name == 'steps' or step_name.startswith('[swarming]') or
          step_name == 'presubmit' or step_name == 'recipe failure reason' or
          (step_name == 'Patch failure' and success_time < failure_time) or
          (step_name == 'bot_update' and 'PATCH FAILED' in step_text) or
          step_name == 'test results' or step_name == 'Uncaught Exception'):
        continue
      failed_steps.append(step)

    steps_to_ignore = []
    for step in failed_steps:
      step_name = step['name']
      if ' (with patch)' in step_name:
        # Android instrumentation tests add a prefix before the step name, which
        # doesn't appear on the summary step (without suffixes). To make sure we
        # correctly ignore duplicate failures, we remove the prefix.
        step_name = step_name.replace('Instrumentation test ', '')

        step_name_with_no_modifier = step_name.replace(' (with patch)', '')
        for other_step in failed_steps:
          # A step which fails, and then is retried and also fails, will have
          # its name without the ' (with patch)' again. Don't double count.
          if other_step['name'] == step_name_with_no_modifier:
            steps_to_ignore.append(other_step['name'])

        # If a step fails without the patch, then the tree is busted. Don't
        # count as flake.
        step_name_without_patch = (
            '%s (without patch)' % step_name_with_no_modifier)
        for other_step in failed_steps:
          if other_step['name'] == step_name_without_patch:
            steps_to_ignore.append(step['name'])
            steps_to_ignore.append(other_step['name'])

    flakes_to_update = []
    for step in failed_steps:
      step_name = step['name']
      if step_name in steps_to_ignore:
        continue
      flakes = self.get_flakes(step)
      if not flakes:
        continue
      for flake in flakes:
        flake_occurrence = FlakeOccurrence(name=step_name, failure=flake)
        flaky_run.flakes.append(flake_occurrence)
        flakes_to_update.append(flake)

    flaky_run_key = flaky_run.put()
    for flake in flakes_to_update:
      self.add_failure_to_flake(flake, flaky_run_key, failure_time)
