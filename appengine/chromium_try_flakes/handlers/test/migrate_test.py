# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from google.appengine.ext import ndb

from handlers.migrate import Migrate
import main
from model.flake import Flake, FlakeOccurrence, FlakeType, FlakyRun, Issue
from model.build_run import BuildRun
from testing_utils import testing


class MigrateTestCase(testing.AppengineTestCase):
  app_module = main.app

  def test_fails_if_existing_flake_types(self):
    FlakeType(project='chromium', step_name='fake_step', test_name=None,
              config=None, last_updated=datetime.datetime.now()).put()
    self.test_app.get('/migrate', status=400)

  def test_ignores_if_issue_id_is_0(self):
    last_updated = datetime.datetime.now()
    Flake(issue_id=0, is_step=True, name='fake_step',
          issue_last_updated=last_updated).put()

    self.test_app.get('/migrate')

    self.assertEqual(len(FlakeType.query().fetch()), 0)

  def test_converts_step_flake(self):
    last_updated = datetime.datetime.now()
    Flake(issue_id=1, is_step=True, name='fake_step',
          issue_last_updated=last_updated).put()

    self.test_app.get('/migrate')

    flake_types = FlakeType.query().fetch()
    self.assertEqual(len(flake_types), 1)

    flake_type = flake_types[0]
    self.assertEqual(flake_type.project, 'chromium')
    self.assertEqual(flake_type.step_name, 'fake_step')
    self.assertIsNone(flake_type.test_name)
    self.assertIsNone(flake_type.config)
    self.assertEqual(flake_type.last_updated, last_updated)

    issues = Issue.query().fetch()
    self.assertEqual(len(issues), 1)

    issue = issues[0]
    self.assertEqual(issue.issue_id, 1)
    self.assertEqual(issue.project, 'chromium')
    self.assertEqual(sorted(issue.flake_type_keys),
                     sorted(flake_type.key for flake_type in flake_types))

  def test_converts_test_flake(self):
    last_updated = datetime.datetime.now()

    fake_build_key = BuildRun(buildnumber=1, result=1,
                              time_finished=last_updated).put()

    flake_run_key = FlakyRun(
        failure_run=fake_build_key,
        success_run=fake_build_key,
        failure_run_time_finished=last_updated,
        flakes=[
            FlakeOccurrence(name='fake_step', failure='fake_test_name'),
            FlakeOccurrence(name='fake_step2', failure='fake_test_name')
    ]).put()

    Flake(issue_id=1, is_step=False, name='fake_test_name',
          issue_last_updated=last_updated, occurrences=[flake_run_key]).put()

    self.test_app.get('/migrate')

    flake_types = FlakeType.query().fetch()
    self.assertEqual(len(flake_types), 2)

    flake_type_1 = flake_types[0]
    self.assertEqual(flake_type_1.project, 'chromium')
    self.assertEqual(flake_type_1.step_name, 'fake_step')
    self.assertEqual(flake_type_1.test_name, 'fake_test_name')
    self.assertIsNone(flake_type_1.config)
    self.assertEqual(flake_type_1.last_updated, last_updated)

    flake_type_2 = flake_types[1]
    self.assertEqual(flake_type_2.project, 'chromium')
    self.assertEqual(flake_type_2.step_name, 'fake_step2')
    self.assertEqual(flake_type_2.test_name, 'fake_test_name')
    self.assertIsNone(flake_type_2.config)
    self.assertEqual(flake_type_2.last_updated, last_updated)

    issues = Issue.query().fetch()
    self.assertEqual(len(issues), 1)

    issue = issues[0]
    self.assertEqual(issue.issue_id, 1)
    self.assertEqual(issue.project, 'chromium')
    self.assertEqual(sorted(issue.flake_type_keys),
                     sorted(flake_type.key for flake_type in flake_types))

  def test_adds_flake_types_only_once(self):
    last_updated = datetime.datetime.now()

    fake_build_key = BuildRun(buildnumber=1, result=1,
                              time_finished=last_updated).put()

    flake_run_key_1 = FlakyRun(
        failure_run=fake_build_key,
        success_run=fake_build_key,
        failure_run_time_finished=last_updated,
        flakes=[
            FlakeOccurrence(name='fake_step', failure='fake_test_name'),
            FlakeOccurrence(name='fake_step2', failure='fake_test_name')
    ]).put()

    flake_run_key_2 = FlakyRun(
        failure_run=fake_build_key,
        success_run=fake_build_key,
        failure_run_time_finished=last_updated,
        flakes=[
            FlakeOccurrence(name='fake_step', failure='fake_test_name'),
    ]).put()

    Flake(issue_id=1, is_step=False, name='fake_test_name',
          issue_last_updated=last_updated, occurrences=[flake_run_key_1]).put()

    Flake(issue_id=2, is_step=False, name='fake_test_name',
          issue_last_updated=last_updated, occurrences=[flake_run_key_2]).put()

    self.test_app.get('/migrate')

    flake_types = FlakeType.query().fetch()
    self.assertEqual(len(flake_types), 2)

    flake_type_1 = flake_types[0]
    self.assertEqual(flake_type_1.project, 'chromium')
    self.assertEqual(flake_type_1.step_name, 'fake_step')
    self.assertEqual(flake_type_1.test_name, 'fake_test_name')
    self.assertIsNone(flake_type_1.config)
    self.assertEqual(flake_type_1.last_updated, last_updated)

    flake_type_2 = flake_types[1]
    self.assertEqual(flake_type_2.project, 'chromium')
    self.assertEqual(flake_type_2.step_name, 'fake_step2')
    self.assertEqual(flake_type_2.test_name, 'fake_test_name')
    self.assertIsNone(flake_type_2.config)
    self.assertEqual(flake_type_2.last_updated, last_updated)

    issues = Issue.query().fetch()
    self.assertEqual(len(issues), 2)

    issue = issues[0]
    self.assertEqual(issue.issue_id, 1)
    self.assertEqual(issue.project, 'chromium')
    self.assertEqual(sorted(issue.flake_type_keys),
                     sorted(flake_type.key for flake_type in flake_types))

    issue = issues[1]
    self.assertEqual(issue.issue_id, 2)
    self.assertEqual(issue.project, 'chromium')
    self.assertEqual(issue.flake_type_keys, [flake_type_1.key])
