# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import mock

from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from services import step_util
from waterfall.test import wf_testcase


class FlakeTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(
      step_util, 'GetCanonicalStepName', return_value='canonical_step_name')
  @mock.patch.object(
      step_util, 'GetIsolateTargetName', return_value='isolate_target_name')
  def testNormalizeStepName(self, mocked_get_isolate_target_name,
                            mocked_get_canonical_step_name):
    self.assertEqual(
        'isolate_target_name',
        Flake.NormalizeStepName(
            step_name='step_name (with patch) on Android',
            master_name='m',
            builder_name='b',
            build_number=200))
    mocked_get_isolate_target_name.assert_called_once(
        master_name='m',
        builder_name='b',
        build_number=200,
        step_name='step_name (with patch) on Android')
    mocked_get_canonical_step_name.assert_not_called()

  @mock.patch.object(
      step_util, 'GetCanonicalStepName', return_value='canonical_step_name')
  @mock.patch.object(
      step_util,
      'GetIsolateTargetName',
      return_value='webkit_layout_tests_exparchive')
  def testNormalizeStepNameForWebkitLayoutTests(
      self, mocked_get_isolate_target_name, mocked_get_canonical_step_name):
    self.assertEqual(
        'webkit_layout_tests',
        Flake.NormalizeStepName(
            step_name='site_per_process_webkit_layout_tests (with patch)',
            master_name='m',
            builder_name='b',
            build_number=200))
    mocked_get_isolate_target_name.assert_called_once(
        master_name='m',
        builder_name='b',
        build_number=200,
        step_name='step_name (with patch) on Android')
    mocked_get_canonical_step_name.assert_not_called()

  @mock.patch.object(
      step_util, 'GetCanonicalStepName', return_value='canonical_step_name')
  @mock.patch.object(step_util, 'GetIsolateTargetName', return_value=None)
  def testNormalizeStepNameIsolateTargetNameIsMissing(
      self, mocked_get_isolate_target_name, mocked_get_canonical_step_name):
    self.assertEqual(
        'canonical_step_name',
        Flake.NormalizeStepName(
            step_name='step_name (with patch) on Android',
            master_name='m',
            builder_name='b',
            build_number=200))
    mocked_get_isolate_target_name.assert_called_once(
        master_name='m',
        builder_name='b',
        build_number=200,
        step_name='step_name (with patch) on Android')
    mocked_get_canonical_step_name.assert_called_once(
        master_name='m',
        builder_name='b',
        build_number=200,
        step_name='step_name (with patch) on Android')

  @mock.patch.object(step_util, 'GetCanonicalStepName', return_value=None)
  @mock.patch.object(step_util, 'GetIsolateTargetName', return_value=None)
  def testNormalizeStepNameCannonicalStepNameIsMissing(
      self, mocked_get_isolate_target_name, mocked_get_canonical_step_name):
    self.assertEqual(
        'step_name',
        Flake.NormalizeStepName(
            step_name='step_name (with patch) on Android',
            master_name='m',
            builder_name='b',
            build_number=200))
    mocked_get_isolate_target_name.assert_called_once(
        master_name='m',
        builder_name='b',
        build_number=200,
        step_name='step_name (with patch) on Android')
    mocked_get_canonical_step_name.assert_called_once(
        master_name='m',
        builder_name='b',
        build_number=200,
        step_name='step_name (with patch) on Android')

  def testNormalizeTestName(self):
    self.assertEqual('suite.test', Flake.NormalizeTestName('suite.test'))

    self.assertEqual('suite.test', Flake.NormalizeTestName('a/suite.test/0',))

    self.assertEqual('suite.test', Flake.NormalizeTestName('suite.test/1'))

    self.assertEqual('suite.test', Flake.NormalizeTestName('suite.test/*'))

    self.assertEqual('suite.test', Flake.NormalizeTestName('*/suite.test/*'))

    self.assertEqual('suite.test',
                     Flake.NormalizeTestName('suite.PRE_PRE_test'))

    self.assertEqual('suite.test',
                     Flake.NormalizeTestName('a/suite.PRE_PRE_test/0'))

    self.assertEqual('a/b/c/d.html', Flake.NormalizeTestName('a/b/c/d.html'))

    self.assertEqual('a/b/c/d.html',
                     Flake.NormalizeTestName('a/b/c/d.html?1000-2000'))

    self.assertEqual('a/b/c/d.html', Flake.NormalizeTestName('a/b/c/d.html?*'))

  def testNormalizeTestNameWithStepName(self):
    self.assertEqual('suite.test', Flake.NormalizeTestName('a/suite.test/1'))

    self.assertEqual('a.html', Flake.NormalizeTestName('a/b.html'))
    self.assertEqual('a/b.html',
                     Flake.NormalizeTestName('a/b.html', 'webkit_layout_tests'))

  def testGetTestLabelName(self):
    self.assertEqual('suite.test',
                     Flake.GetTestLabelName('suite.test', 'base_unittests'))

    self.assertEqual('suite.test/*',
                     Flake.GetTestLabelName('suite.test/1', 'base_unittests'))

    self.assertEqual('*/suite.test/*',
                     Flake.GetTestLabelName('a/suite.test/0', 'base_unittests'))

    self.assertEqual(
        'suite.*test',
        Flake.GetTestLabelName('suite.PRE_PRE_test', 'base_unittests'))

    self.assertEqual(
        '*/suite.*test/*',
        Flake.GetTestLabelName('a/suite.PRE_PRE_test/0', 'base_unittests'))

    self.assertEqual('a/b.html',
                     Flake.NormalizeTestName('a/b.html', 'webkit_layout_tests'))

    self.assertEqual(
        'a/b.html?*',
        Flake.GetTestLabelName('a/b.html?1000-2000', 'webkit_layout_tests'))

  def testGetId(self):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step'
    normalized_test_name = 'normalized_test'
    self.assertEqual(
        'chromium@normalized_step@normalized_test',
        Flake.GetId(
            luci_project=luci_project,
            normalized_step_name=normalized_step_name,
            normalized_test_name=normalized_test_name))

  def testCreate(self):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step'
    normalized_test_name = 'normalized_test'
    test_label_name = 'test_label'

    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)

    flake.put()

    fetched_flakes = Flake.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(flake, fetched_flakes[0])

  def testGet(self):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step'
    normalized_test_name = 'normalized_test'
    test_label_name = 'test_label'

    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)

    flake.put()

    retrieved_flake = Flake.Get(luci_project, normalized_step_name,
                                normalized_test_name)
    self.assertIsNotNone(retrieved_flake)
    self.assertEqual(normalized_test_name, retrieved_flake.normalized_test_name)
    self.assertEqual(normalized_step_name, retrieved_flake.normalized_step_name)

  def testGetIssue(self):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step'
    normalized_test_name = 'a/b.html'
    test_label_name = 'test_label'
    bug_id = 12345

    flake_issue = FlakeIssue.Create(luci_project, bug_id)
    flake_issue.put()
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)
    flake.flake_issue_key = flake_issue.key
    self.assertEqual(flake_issue, flake.GetIssue())

  def testGetIssueNoIssue(self):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step'
    normalized_test_name = 'a/b.html'
    test_label_name = 'test_label'

    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)

    self.assertIsNone(flake.GetIssue())

  def testGetTestSuiteName(self):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step'
    normalized_test_name = 'a/b.html'
    test_label_name = 'test_label'

    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)
    flake.tags.append('suite::a')
    flake.put()
    self.assertEqual('a', flake.GetTestSuiteName())

  def testGetFlakeIssueDataInconsistent(self):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake_issue_key = flake_issue.key
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='suite.test',
        test_label_name='*/suite.test/*')
    flake.flake_issue_key = flake_issue_key
    flake.put()

    flake_issue_key.delete()

    self.assertIsNone(flake.GetIssue())

  def testGetFlakeIssueNoIssueKey(self):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='suite.test',
        test_label_name='*/suite.test/*')
    flake.put()

    self.assertIsNone(flake.GetIssue())

  def testGetFlakeIssue(self):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake_issue_key = flake_issue.key
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='suite.test',
        test_label_name='*/suite.test/*')
    flake.flake_issue_key = flake_issue_key
    flake.put()

    self.assertEqual(flake_issue_key,
                     flake.GetIssue(up_to_date=True, key_only=True))
