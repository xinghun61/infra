# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the moved project notification page servlet."""

import unittest

import webapp2

from services import service_manager
from sitewide import moved
from testing import fake
from testing import testing_helpers


class MovedTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService())
    self.servlet = moved.ProjectMoved('req', 'res', services=self.services)

  def testGatherPageData(self):
    project_name = 'my-project'
    moved_to = 'http://we-are-outta-here.com/'
    _request, mr = testing_helpers.GetRequestObjects(
        path='/hosting/moved?project=my-project')

    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet.GatherPageData(mr)
    self.assertEquals(404, cm.exception.code)

    project = self.services.project.TestAddProject(project_name)
    # Project exists but has not been moved, so 400 BAD_REQUEST.
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet.GatherPageData(mr)
    self.assertEquals(400, cm.exception.code)

    # Display the moved_to url if it is valid.
    project.moved_to = moved_to
    page_data = self.servlet.GatherPageData(mr)
    self.assertItemsEqual(
        ['project_name', 'moved_to_url'],
        page_data.keys())
    self.assertEqual(project_name, page_data['project_name'])
    self.assertEqual(moved_to, page_data['moved_to_url'])

    # We only display URLs that start with 'http'.
    project.moved_to = 'javascript:alert(1)'
    page_data = self.servlet.GatherPageData(mr)
    self.assertItemsEqual(
        ['project_name', 'moved_to_url'],
        page_data.keys())
    self.assertEqual(project_name, page_data['project_name'])
    self.assertEqual('#invalid-destination-url', page_data['moved_to_url'])


if __name__ == '__main__':
  unittest.main()
