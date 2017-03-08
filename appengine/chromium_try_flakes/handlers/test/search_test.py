# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

import main
from model.flake import Flake


class TestSearch(testing.AppengineTestCase):
  app_module = main.app

  def test_fails_to_find_flake(self):
    response = self.test_app.get('/search?q=unknown-flake')
    self.assertEqual(response.body, 'No flake entry found for unknown-flake')

  def test_redirects_to_all_flake_occurrences(self):
    key = Flake(name='foo').put()
    response = self.test_app.get('/search?q=foo', status=302)
    self.assertIn('location', response.headers)
    self.assertTrue(response.headers['location'].endswith(
      '/all_flake_occurrences?key=%s' % key.urlsafe()))

  def test_normalizes_step_name(self):
    key = Flake(name='my_unittests (with patch)').put()
    response = self.test_app.get(
        '/search?q=my_unittests+(with+patch)+on+NVIDIA+GPU', status=302)
    self.assertIn('location', response.headers)
    self.assertTrue(response.headers['location'].endswith(
      '/all_flake_occurrences?key=%s' % key.urlsafe()))
