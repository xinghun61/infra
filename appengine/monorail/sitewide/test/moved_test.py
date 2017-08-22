# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the moved project notification page servlet."""

import unittest

import webapp2

from framework import exceptions
from services import service_manager
from sitewide import moved
from testing import fake
from testing import testing_helpers


class MovedTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService())
    self.servlet = moved.ProjectMoved('req', 'res', services=self.services)
    self.old_project = 'old-project'

  def testGatherPageData_NoProjectSpecified(self):
    # Project was not included in URL, so raise exception, will cause 400.
    _, mr = testing_helpers.GetRequestObjects(
        path='/hosting/moved')

    with self.assertRaises(exceptions.InputException):
      self.servlet.GatherPageData(mr)

  def testGatherPageData_NoSuchProject(self):
    # Project doesn't exist, so 404 NOT FOUND.
    _, mr = testing_helpers.GetRequestObjects(
        path='/hosting/moved?project=nonexistent')

    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet.GatherPageData(mr)
    self.assertEquals(404, cm.exception.code)

  def testGatherPageData_NotMoved(self):
    # Project exists but has not been moved, so 400 BAD_REQUEST.
    self.services.project.TestAddProject(self.old_project)
    _, mr = testing_helpers.GetRequestObjects(
        path='/hosting/moved?project=%s' % self.old_project)

    with self.assertRaises(webapp2.HTTPException) as cm:
      self.servlet.GatherPageData(mr)
    self.assertEquals(400, cm.exception.code)

  def testGatherPageData_URL(self):
    # Display the moved_to url if it is valid.
    project = self.services.project.TestAddProject(self.old_project)
    project.moved_to = 'https://other-tracker.bugs'
    _, mr = testing_helpers.GetRequestObjects(
        path='/hosting/moved?project=%s' % self.old_project)

    page_data = self.servlet.GatherPageData(mr)
    self.assertItemsEqual(
        ['project_name', 'moved_to_url'],
        page_data.keys())
    self.assertEqual(self.old_project, page_data['project_name'])
    self.assertEqual('https://other-tracker.bugs', page_data['moved_to_url'])

  def testGatherPageData_ProjectName(self):
    # Construct the moved-to url from just the project name.
    project = self.services.project.TestAddProject(self.old_project)
    project.moved_to = 'new-project'
    _, mr = testing_helpers.GetRequestObjects(
        path='/hosting/moved?project=%s' % self.old_project)

    page_data = self.servlet.GatherPageData(mr)
    self.assertItemsEqual(
        ['project_name', 'moved_to_url'],
        page_data.keys())
    self.assertEqual(self.old_project, page_data['project_name'])
    self.assertEqual('http://127.0.0.1/p/new-project/',
                     page_data['moved_to_url'])

  def testGatherPageData_HttpProjectName(self):
    # A project named "http-foo" gets treated as a project, not a url.
    project = self.services.project.TestAddProject(self.old_project)
    project.moved_to = 'http-project'
    _, mr = testing_helpers.GetRequestObjects(
        path='/hosting/moved?project=%s' % self.old_project)

    page_data = self.servlet.GatherPageData(mr)
    self.assertItemsEqual(
        ['project_name', 'moved_to_url'],
        page_data.keys())
    self.assertEqual(self.old_project, page_data['project_name'])
    self.assertEqual('http://127.0.0.1/p/http-project/',
                     page_data['moved_to_url'])

  def testGatherPageData_BadScheme(self):
    # We only display URLs that start with 'http(s)://'.
    project = self.services.project.TestAddProject(self.old_project)
    project.moved_to = 'javascript:alert(1)'
    _, mr = testing_helpers.GetRequestObjects(
        path='/hosting/moved?project=%s' % self.old_project)

    page_data = self.servlet.GatherPageData(mr)
    self.assertItemsEqual(
        ['project_name', 'moved_to_url'],
        page_data.keys())
    self.assertEqual(self.old_project, page_data['project_name'])
    self.assertEqual('#invalid-destination-url', page_data['moved_to_url'])
