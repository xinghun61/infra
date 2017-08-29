# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the custom_404 servlet."""

import httplib
import unittest

from framework import exceptions
from services import service_manager
from sitewide import custom_404
from testing import fake
from testing import testing_helpers


class Custom404Test(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService())
    self.servlet = custom_404.ErrorPage('req', 'res', services=self.services)

  def testGatherPageData_NoProjectSpecified(self):
    """Project was not included in URL, so raise exception, will cause 400."""
    _, mr = testing_helpers.GetRequestObjects(
        path='/not/a/project/url')

    with self.assertRaises(exceptions.InputException):
      self.servlet.GatherPageData(mr)

  def testGatherPageData_Normal(self):
    """Return page_data dict with a 404 response code specified."""
    _project = self.services.project.TestAddProject('proj')
    _, mr = testing_helpers.GetRequestObjects(path='/p/proj/junk')

    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(
      {'http_response_code': httplib.NOT_FOUND},
      page_data)
