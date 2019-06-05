# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for monorail.tracker.issueadvsearch."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issueadvsearch

class IssueAdvSearchTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        features=fake.FeaturesService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService())
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    self.servlet = issueadvsearch.IssueAdvancedSearch(
        'req', 'res', services=self.services)

  def testGatherData(self):
    mr = testing_helpers.MakeMonorailRequest(
      path='/p/proj/issues/advsearch')
    page_data = self.servlet.GatherPageData(mr)

    self.assertTrue('issue_tab_mode' in page_data)
    self.assertTrue('page_perms' in page_data)

  def testProcessFormData(self):
    mr = testing_helpers.MakeMonorailRequest(
      path='/p/proj/issues/advsearch')
    post_data = {}
    url = self.servlet.ProcessFormData(mr, post_data)
    self.assertTrue('can=2' in url)

    post_data['can'] = 42
    url = self.servlet.ProcessFormData(mr, post_data)
    self.assertTrue('can=42' in url)

    post_data['starcount'] = 42
    url = self.servlet.ProcessFormData(mr, post_data)
    self.assertTrue('starcount%3A42' in url)

    post_data['starcount'] = -1
    url = self.servlet.ProcessFormData(mr, post_data)
    self.assertTrue('starcount' not in url)

  def _testAND(self, operator, field, post_data, query):
    self.servlet._AccumulateANDTerm(operator, field, post_data, query)
    return query

  def test_AccumulateANDTerm(self):
    query = self._testAND('', 'foo', {'foo':'bar'}, [])
    self.assertEquals(['bar'], query)

    query = self._testAND('', 'bar', {'bar':'baz=zippy'}, query)
    self.assertEquals(['bar', 'baz', 'zippy'], query)

  def _testOR(self, operator, field, post_data, query):
    self.servlet._AccumulateORTerm(operator, field, post_data, query)
    return query

  def test_AccumulateORTerm(self):
    query = self._testOR('', 'foo', {'foo':'bar'}, [])
    self.assertEquals(['bar'], query)

    query = self._testOR('', 'bar', {'bar':'baz=zippy'}, query)
    self.assertEquals(['bar', 'baz,zippy'], query)

