# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for component prediction endpoints."""

import json
import sys
import unittest

from mock import Mock, patch
from StringIO import StringIO

from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers

# Mock cloudstorage before it's imported by componentpredict.
sys.modules['cloudstorage'] = Mock()
from features import componentpredict


class ComponentPredictTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        user=fake.UserService())
    self.project = fake.Project(project_name='proj')
    self.services.user.TestAddUser('test@example.com', 111L)
    self.servlet = componentpredict.ComponentPredict(
        'req', 'res', services=self.services)
    self.servlet.mr = testing_helpers.MakeMonorailRequest(
        path='/', project=self.project, method='GET')

  @patch('features.componentpredict.ComponentPredict.GetPrediction')
  @patch('features.componentpredict.ComponentPredict.GetComponentID')
  def testPredict_Normal(self, mockGetComponentID, _mockGetPrediction):
    """Test normal case when predicted component exists."""
    component_id = self.services.config.CreateComponentDef(
        cnxn=None, project_id=self.project.project_id, path='Ruta>Baga',
        docstring='', deprecated=False, admin_ids=[], cc_ids=[], created=None,
        creator_id=None, label_ids=[])
    mockGetComponentID.return_value = component_id
    actual = self.servlet.Predict(
        instance={}, ml_engine=None, model_name='a', trainer_name='b')
    self.assertEqual(1, len(actual['components']))
    self.assertEqual('Ruta>Baga', actual['components'][0])

  @patch('features.componentpredict.ComponentPredict.GetPrediction')
  @patch('features.componentpredict.ComponentPredict.GetComponentID')
  def testPredict_SoftDeleted(self, mockGetComponentID, _mockGetPrediction):
    """Referring to a component ID that doesn't exist in the config. This
    would be the case when a component is soft-deleted."""
    component_id = 987
    mockGetComponentID.return_value = component_id
    actual = self.servlet.Predict(instance={}, ml_engine=None, model_name='a',
        trainer_name='b')
    self.assertEqual(0, len(actual['components']))

  @patch('cloudstorage.open')
  def testGetComponentID(self, mockCloudstorageOpen):
    """Important: must convert IDs stored as strings to longs."""
    mock_file = StringIO(json.dumps({
      '321': '987',
      '123': '789',
    }))
    mockCloudstorageOpen.return_value = mock_file

    component_id = self.servlet.GetComponentID(trainer_name='trainer',
        index=123)
    self.assertIsInstance(component_id, long)
    self.assertEqual(789, component_id)
