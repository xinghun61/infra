# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging
import mock
from StringIO import StringIO

import cloudstorage as gcs

from waterfall.test import wf_testcase

from services import step_util
from services import swarmed_test_util
from services.flake_reporting import test_location


class TestLocationTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(swarmed_test_util, 'GetTestLocation')
  @mock.patch.object(step_util, 'GetStepMetadata')
  @mock.patch.object(test_location, '_GetComponentAndTeamMapping')
  def testGetComponentNew(self, mock_component, mock_metadata,
                          mock_test_location):

    flake = mock.Mock()
    flake.step_name = 'some step'
    flake.test_name = 'SomeTest'
    flake.parent.normalized_test_name = flake.test_name
    flake.parent.test_location.file_path = None
    flake.build_configuration.legacy_master_name = 'some.master'
    flake.build_configuration.luci_builder = 'Some Builder (dbg)'
    flake.build_configuration.legacy_build_number = 42

    mock_component.return_value = {
        'dir-to-component': {
            'some/fake/path': 'Mock>Component'
        }
    }

    location = mock.Mock()
    location.file = '../../some/fake/path/abc.cc'
    location.line = 0

    mock_metadata.return_value = {'swarm_task_ids': ['mock_swarm_id']}
    mock_test_location.return_value = location

    test_location.UpdateFlakeComponent(flake)

    self.assertEqual(
        mock.call('some.master', 'Some Builder (dbg)', 42, 'some step'),
        mock_metadata.call_args)
    self.assertEqual(
        mock.call('mock_swarm_id', 'SomeTest'), mock_test_location.call_args)
    self.assertIn('some/fake/path', flake.parent.test_location.file_path)
    self.assertEqual('Mock>Component', flake.parent.component)

  @mock.patch.object(swarmed_test_util, 'GetTestLocation')
  @mock.patch.object(step_util, 'GetStepMetadata')
  @mock.patch.object(test_location, '_GetComponentAndTeamMapping')
  def testGetComponentExisting(self, mock_component, mock_metadata,
                               mock_test_location):

    flake = mock.Mock()
    flake.step_name = 'some step'
    flake.test_name = 'SomeOtherTest'
    flake.parent.normalized_test_name = flake.test_name
    flake.build_configuration.legacy_master_name = 'some.master'
    flake.build_configuration.luci_builder = 'Some Builder (dbg)'
    flake.build_configuration.legacy_build_number = 42

    mock_component.return_value = {
        'dir-to-component': {
            'some/other/fake/path': 'Mock>Component'
        }
    }

    flake.parent.test_location.file_path = '../../some/other/fake/path/abc.cc'
    flake.parent.test_location.line_number = 0

    test_location.UpdateFlakeComponent(flake)

    self.assertIsNone(mock_metadata.call_args)
    self.assertIsNone(mock_test_location.call_args)
    self.assertEqual('Mock>Component', flake.parent.component)

  @mock.patch.object(logging, 'error')
  @mock.patch.object(swarmed_test_util, 'GetTestLocation')
  @mock.patch.object(step_util, 'GetStepMetadata')
  @mock.patch.object(test_location, '_GetComponentAndTeamMapping')
  def testGetComponentFailure(self, _mock_component, mock_metadata,
                              mock_test_location, mock_error):

    flake = mock.Mock()
    flake.step_name = 'some step'
    flake.test_name = 'SomeTest'
    flake.parent.normalized_test_name = flake.test_name
    flake.parent.test_location.file_path = None
    flake.parent.test_location.line_number = None
    flake.build_configuration.legacy_master_name = 'some.master'
    flake.build_configuration.luci_builder = 'Some Builder (dbg)'
    flake.build_configuration.legacy_build_number = 42

    mock_metadata.return_value = {'swarm_task_ids': ['mock_swarm_id']}
    mock_test_location.return_value = None

    test_location.UpdateFlakeComponent(flake)

    self.assertEqual('Unknown', flake.parent.component)
    self.assertEqual(1, mock_error.call_count)
    self.assertEqual(
        mock.call('some.master', 'Some Builder (dbg)', 42, 'some step'),
        mock_metadata.call_args)
    self.assertEqual(
        mock.call('mock_swarm_id', 'SomeTest'), mock_test_location.call_args)
    self.assertIsNone(flake.parent.test_location.file_path)

  @mock.patch.object(gcs, 'open')
  def testGetMapping(self, mock_gcs):
    dummy_mapping = {
        'dir-to-component': {
            'some/fake/path': 'Fake > Component',
            'some/other/fake/path': 'Teamless > Component'
        },
        'component-to-team': {
            'Fake > Component': 'fake@team.org'
        }
    }
    mock_gcs.return_value = StringIO(json.dumps(dummy_mapping))
    mapping = test_location._GetComponentAndTeamMapping()
    self.assertEqual(dummy_mapping, mapping)
    _another_copy = test_location._GetComponentAndTeamMapping()
    # Caching should make it so that we only call gcs once.
    self.assertEqual(1, mock_gcs.call_count)

    component = test_location._GetComponentForPath('../some/fake/path/abc.c')
    self.assertEqual(component, 'Fake > Component')

    component = test_location._GetComponentForPath(
        '../some/other/fake/path/x.mm')
    self.assertEqual(component, 'Teamless > Component')

    component = test_location._GetComponentForPath(
        '../some/unknown/fake/path/d.cc')
    self.assertEqual(component, 'Unknown')
