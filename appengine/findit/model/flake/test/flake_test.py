# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import mock

from model.flake.flake import Flake
from services import ci_failure
from waterfall.test import wf_testcase


class FlakeTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(
      ci_failure, 'GetCanonicalStepName', return_value='canonical_step_name')
  @mock.patch.object(
      ci_failure, 'GetIsolateTargetName', return_value='isolate_target_name')
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
      ci_failure, 'GetCanonicalStepName', return_value='canonical_step_name')
  @mock.patch.object(
      ci_failure,
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
      ci_failure, 'GetCanonicalStepName', return_value='canonical_step_name')
  @mock.patch.object(ci_failure, 'GetIsolateTargetName', return_value=None)
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

  @mock.patch.object(ci_failure, 'GetCanonicalStepName', return_value=None)
  @mock.patch.object(ci_failure, 'GetIsolateTargetName', return_value=None)
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

    self.assertEqual('suite.test', Flake.NormalizeTestName('a/suite.test/0'))

    self.assertEqual('suite.test', Flake.NormalizeTestName('*/suite.test/*'))

    self.assertEqual('suite.test', Flake.NormalizeTestName('suite.test/1'))

    self.assertEqual('suite.test', Flake.NormalizeTestName('suite.test/*'))

    self.assertEqual('suite.test',
                     Flake.NormalizeTestName('suite.PRE_PRE_test'))

    self.assertEqual('suite.test',
                     Flake.NormalizeTestName('a/suite.PRE_PRE_test/0'))

    self.assertEqual('a/b.html', Flake.NormalizeTestName('a/b.html'))

    self.assertEqual('a/b.html', Flake.NormalizeTestName('a/b.html?1000-2000'))

    self.assertEqual('a/b.html', Flake.NormalizeTestName('a/b.html?*'))

  def testGetTestLabelName(self):
    self.assertEqual('suite.test', Flake.GetTestLabelName('suite.test'))

    self.assertEqual('suite.test/*', Flake.GetTestLabelName('suite.test/1'))

    self.assertEqual('*/suite.test/*', Flake.GetTestLabelName('a/suite.test/0'))

    self.assertEqual('suite.*test',
                     Flake.GetTestLabelName('suite.PRE_PRE_test'))

    self.assertEqual('*/suite.*test/*',
                     Flake.GetTestLabelName('a/suite.PRE_PRE_test/0'))

    self.assertEqual('a/b.html', Flake.NormalizeTestName('a/b.html'))

    self.assertEqual('a/b.html?*', Flake.GetTestLabelName('a/b.html?1000-2000'))

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

  def testComputeTestSuiteName(self):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step'
    normalized_test_name = 'suite.test'
    test_label_name = 'test_label'

    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)

    flake.put()

    fetched_flakes = Flake.query(Flake.test_suite_name == 'suite').fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual('suite', fetched_flakes[0].test_suite_name)

  def testTestSuiteNameIsNoneForWebkitLayoutTests(self):
    luci_project = 'chromium'
    normalized_step_name = 'normalized_step'
    normalized_test_name = 'a/b.html'
    test_label_name = 'test_label'

    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)

    flake.put()

    fetched_flakes = Flake.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(None, fetched_flakes[0].test_suite_name)
