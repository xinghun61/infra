# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for component prediction endpoints."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import mock
import sys
import unittest

from services import service_manager
from testing import fake

# Mock cloudstorage before it's imported by component_helpers
sys.modules['cloudstorage'] = mock.Mock()
from features import component_helpers


class FakeMLEngine(object):
  def __init__(self, test):
    self.test = test
    self.expected_features = None
    self.scores = None
    self._execute_response = None

  def projects(self):
    return self

  def models(self):
    return self

  def predict(self, name, body):
    self.test.assertEqual(component_helpers.MODEL_NAME, name)
    self.test.assertEqual(
        {'instances': [{'inputs': self.expected_features}]}, body)
    self._execute_response = {'predictions': [{'scores': self.scores}]}
    return self

  def get(self, name):
    self.test.assertEqual(component_helpers.MODEL_NAME, name)
    self._execute_response = {'defaultVersion': {'name': 'v_1234'}}
    return self

  def execute(self):
    response = self._execute_response
    self._execute_response = None
    return response


class ComponentHelpersTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        user=fake.UserService())
    self.project = fake.Project(project_name='proj')

    self._ml_engine = FakeMLEngine(self)
    self._top_words = None
    self._components_by_index = None

    mock.patch(
        'services.ml_helpers.setup_ml_engine', lambda: self._ml_engine).start()
    mock.patch(
        'features.component_helpers._GetTopWords',
        lambda _: self._top_words).start()
    mock.patch('cloudstorage.open', self.cloudstorageOpen).start()
    mock.patch('settings.component_features', 5).start()

    self.addCleanup(mock.patch.stopall)

  def cloudstorageOpen(self, name, mode):
    """Create a file mock that returns self._components_by_index when read."""
    open_fn = mock.mock_open(read_data=json.dumps(self._components_by_index))
    return open_fn(name, mode)

  def testPredict_Normal(self):
    """Test normal case when predicted component exists."""
    component_id = self.services.config.CreateComponentDef(
        cnxn=None, project_id=self.project.project_id, path='Ruta>Baga',
        docstring='', deprecated=False, admin_ids=[], cc_ids=[], created=None,
        creator_id=None, label_ids=[])
    config = self.services.config.GetProjectConfig(
        None, self.project.project_id)

    self._top_words = {
        'foo': 0,
        'bar': 1,
        'baz': 2}
    self._components_by_index = {
        '0': '123',
        '1': str(component_id),
        '2': '789'}
    self._ml_engine.expected_features = [3, 0, 1, 0, 0]
    self._ml_engine.scores = [5, 10, 3]

    text = 'foo baz foo foo'

    self.assertEqual(
        component_id, component_helpers.PredictComponent(text, config))

  def testPredict_UnknownComponentIndex(self):
    """Test case where the prediction is not in components_by_index."""
    config = self.services.config.GetProjectConfig(
        None, self.project.project_id)

    self._top_words = {
        'foo': 0,
        'bar': 1,
        'baz': 2}
    self._components_by_index = {
        '0': '123',
        '1': '456',
        '2': '789'}
    self._ml_engine.expected_features = [3, 0, 1, 0, 0]
    self._ml_engine.scores = [5, 10, 3, 1000]

    text = 'foo baz foo foo'

    self.assertIsNone(component_helpers.PredictComponent(text, config))

  def testPredict_InvalidComponentIndex(self):
    """Test case where the prediction is not a valid component id."""
    config = self.services.config.GetProjectConfig(
        None, self.project.project_id)

    self._top_words = {
        'foo': 0,
        'bar': 1,
        'baz': 2}
    self._components_by_index = {
        '0': '123',
        '1': '456',
        '2': '789'}
    self._ml_engine.expected_features = [3, 0, 1, 0, 0]
    self._ml_engine.scores = [5, 10, 3]

    text = 'foo baz foo foo'

    self.assertIsNone(component_helpers.PredictComponent(text, config))
