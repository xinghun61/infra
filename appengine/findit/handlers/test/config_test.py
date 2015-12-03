# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

import webapp2

from handlers import config
from model import wf_config
from testing_utils import testing


_MOCK_MASTERS_TO_BLACKLISTED_STEPS = {
    'master1': ['unsupported_step1', 'unsupported_step2'],
    'master2': ['unsupported_step3', 'unsupported_step4'],
}

_MOCK_BUILDERS_TO_TRYBOTS = {
    'master1': {
        'builder1': {
            'mastername': 'tryserver1',
            'buildername': 'trybot1',
        }
    }
}

_MOCK_VERSION_NUMBER = 12


class ConfigTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/config', config.Configuration),
  ], debug=True)

  def testGetConfigurationSettings(self):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    config_data = {
        'masters_to_blacklisted_steps': _MOCK_MASTERS_TO_BLACKLISTED_STEPS,
        'builders_to_trybots': _MOCK_BUILDERS_TO_TRYBOTS,
    }
    wf_config.FinditConfig.Get().Update(**config_data)

    response = self.test_app.get('/config', params={'format': 'json'})
    self.assertEquals(response.status_int, 200)

    expected_response = {
        'masters': _MOCK_MASTERS_TO_BLACKLISTED_STEPS,
        'builders': _MOCK_BUILDERS_TO_TRYBOTS,
        'version': 1,
    }

    self.assertEquals(expected_response, response.json_body)

  def testValidateMastersDict(self):
    self.assertTrue(config._SupportedMastersConfigIsValid({
        'a': ['string1', 'string2', 'string3'],
        'b': ['string1', 'string2', 'string3'],
    }))
    self.assertFalse(config._SupportedMastersConfigIsValid({
        'a': {}
    }))
    self.assertFalse(config._SupportedMastersConfigIsValid({
        'a': [1, 2, 3]
    }))
    self.assertFalse(config._SupportedMastersConfigIsValid([]))
    self.assertFalse(config._SupportedMastersConfigIsValid([{
        'a': ['b', 'c', 'd']
    }]))

  def testValidateTrybotMapping(self):
    self.assertTrue(config._ValidateTrybotMapping({
        'master1': {
            'builder1': {
                'mastername': 'tryserver1',
                'buildername': 'trybot1',
            }
        }
    }))
    self.assertFalse(config._ValidateTrybotMapping(['a']))
    self.assertFalse(config._ValidateTrybotMapping({'a': ['b']}))
    self.assertFalse(config._ValidateTrybotMapping({'a': {'b':['1']}}))
    self.assertFalse(config._ValidateTrybotMapping({'a': {'b': {}}}))

  def testConfigurationDictIsValid(self):
    self.assertTrue(config._ConfigurationDictIsValid({
        'masters_to_blacklisted_steps': {
            'a': []
        }
    }))
    self.assertFalse(config._ConfigurationDictIsValid([]))
    self.assertFalse(config._ConfigurationDictIsValid({
        'this_is_not_a_valid_property': []
    }))

  def testPostConfigurationSettings(self):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    params = {
        'format': 'json',
        'data': json.dumps({
            'masters_to_blacklisted_steps': {
                'a': ['1', '2', '3'],
                'b': [],
            },
            'builders_to_trybots': _MOCK_BUILDERS_TO_TRYBOTS,
        })
    }

    expected_response = {
        'masters': {
            'a': ['1', '2', '3'],
            'b': []
        },
        'builders': _MOCK_BUILDERS_TO_TRYBOTS,
        'version': 1,
    }

    response = self.test_app.post('/config', params=params)
    self.assertEquals(expected_response, response.json_body)
