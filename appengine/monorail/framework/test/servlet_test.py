# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for servlet base class module."""

import time
import unittest

from google.appengine.ext import testbed

import webapp2

from framework import framework_constants
from framework import servlet
from framework import xsrf
from proto import project_pb2
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class TestableServlet(servlet.Servlet):
  """A tiny concrete subclass of abstract class Servlet."""

  def __init__(self, request, response, services=None, do_post_redirect=True):
    super(TestableServlet, self).__init__(request, response, services=services)
    self.do_post_redirect = do_post_redirect
    self.seen_post_data = None

  def ProcessFormData(self, _mr, post_data):
    self.seen_post_data = post_data
    if self.do_post_redirect:
      return '/This/Is?The=Next#Page'
    else:
      self.response.write('sending raw data to browser')


class ServletTest(unittest.TestCase):

  def setUp(self):
    services = service_manager.Services(project=fake.ProjectService())
    self.page_class = TestableServlet(
        webapp2.Request.blank('/'), webapp2.Response(), services=services)
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def testDefaultValues(self):
    self.assertEqual(None, self.page_class._MAIN_TAB_MODE)
    self.assertTrue(self.page_class._TEMPLATE_PATH.endswith('/templates/'))
    self.assertEqual(None, self.page_class._PAGE_TEMPLATE)

  def testGatherBaseData(self):
    project = fake.Project(
        project_name='testproj', cached_content_timestamp=12345,
        state=project_pb2.ProjectState.LIVE)

    (_request, mr) = testing_helpers.GetRequestObjects(
        path='/p/testproj/feeds', project=project)
    nonce = '1a2b3c4d5e6f7g'

    base_data = self.page_class.GatherBaseData(mr, nonce)

    self.assertEqual(base_data['nonce'], nonce)
    self.assertEqual(base_data['projectname'], 'testproj')
    self.assertEqual(base_data['project'].cached_content_timestamp, 12345)
    self.assertEqual(base_data['project_alert'], None)

    self.assert_(
        base_data['currentPageURL'].endswith('/p/testproj/feeds'))
    self.assert_(
        base_data['currentPageURLEncoded'].endswith('%2Fp%2Ftestproj%2Ffeeds'))

  def testFormHandlerURL(self):
    self.assertEqual('/edit.do', self.page_class._FormHandlerURL('/'))
    self.assertEqual(
      '/something/edit.do',
      self.page_class._FormHandlerURL('/something/'))
    self.assertEqual(
      '/something/edit.do',
      self.page_class._FormHandlerURL('/something/edit.do'))
    self.assertEqual(
      '/something/detail.do',
      self.page_class._FormHandlerURL('/something/detail'))

  def testProcessForm_NoToken(self):
    user_id = 111L
    request, mr = testing_helpers.GetRequestObjects(
        path='/we/we/we?so=excited',
        params={'yesterday': 'thursday', 'today': 'friday'},
        user_info={'user_id': user_id},
        method='POST',
    )
    # Normally, every form needs a security token.
    self.assertRaises(
        xsrf.TokenIncorrect, self.page_class._DoFormProcessing, request, mr)
    self.assertEqual(None, self.page_class.seen_post_data)

    # We can make an explicit exception to that.
    self.page_class.CHECK_SECURITY_TOKEN = False
    try:
      self.page_class._DoFormProcessing(request, mr)
      self.fail()
    except webapp2.HTTPException as e:
      self.assertEqual(302, e.code)  # forms redirect on succcess

    self.assertDictEqual(
        {'yesterday': 'thursday', 'today': 'friday'},
        dict(self.page_class.seen_post_data))

  def testProcessForm_BadToken(self):

    user_id = 111L
    token = 'no soup for you'

    request, mr = testing_helpers.GetRequestObjects(
        path='/we/we/we?so=excited',
        params={'yesterday': 'thursday', 'today': 'friday', 'token': token},
        user_info={'user_id': user_id},
        method='POST',
    )
    self.assertRaises(
        xsrf.TokenIncorrect, self.page_class._DoFormProcessing, request, mr)
    self.assertEqual(None, self.page_class.seen_post_data)

  def testProcessForm_Normal(self):
    user_id = 111L
    token = xsrf.GenerateToken(user_id, '/we/we/we')

    request, mr = testing_helpers.GetRequestObjects(
        path='/we/we/we?so=excited',
        params={'yesterday': 'thursday', 'today': 'friday', 'token': token},
        user_info={'user_id': user_id},
        method='POST',
    )
    try:
      self.page_class._DoFormProcessing(request, mr)
      self.fail()
    except webapp2.HTTPException as e:
      self.assertEqual(302, e.code)  # forms redirect on succcess

    self.assertDictEqual(
        {'yesterday': 'thursday', 'today': 'friday', 'token': token},
        dict(self.page_class.seen_post_data))

  def testCalcProjectAlert(self):
    project = fake.Project(
        project_name='alerttest', state=project_pb2.ProjectState.LIVE)

    project_alert = servlet._CalcProjectAlert(project)
    self.assertEqual(project_alert, None)

    project.state = project_pb2.ProjectState.ARCHIVED
    project_alert = servlet._CalcProjectAlert(project)
    self.assertEqual(
        project_alert,
        'Project is archived: read-only by members only.')

    delete_time = int(time.time() + framework_constants.SECS_PER_DAY * 1.5)
    project.delete_time = delete_time
    project_alert = servlet._CalcProjectAlert(project)
    self.assertEqual(project_alert, 'Scheduled for deletion in 1 day.')

    delete_time = int(time.time() + framework_constants.SECS_PER_DAY * 2.5)
    project.delete_time = delete_time
    project_alert = servlet._CalcProjectAlert(project)
    self.assertEqual(project_alert, 'Scheduled for deletion in 2 days.')

  def testCheckForMovedProject_NoRedirect(self):
    project = fake.Project(
        project_name='proj', state=project_pb2.ProjectState.LIVE)
    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj', project=project)
    self.page_class._CheckForMovedProject(mr, request)

    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/source/browse/p/adminAdvanced', project=project)
    self.page_class._CheckForMovedProject(mr, request)

  def testCheckForMovedProject_Redirect(self):
    project = fake.Project(project_name='proj', moved_to='http://example.com')
    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj', project=project)
    try:
      self.page_class._CheckForMovedProject(mr, request)
      self.fail()
    except webapp2.HTTPException as e:
      self.assertEqual(302, e.code)  # redirect because project moved

    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/source/browse/p/adminAdvanced', project=project)
    try:
      self.page_class._CheckForMovedProject(mr, request)
      self.fail()
    except webapp2.HTTPException as e:
      self.assertEqual(302, e.code)  # redirect because project moved

  def testCheckForMovedProject_AdminAdvanced(self):
    """We do not redirect away from the page that edits project state."""
    project = fake.Project(project_name='proj', moved_to='http://example.com')
    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/adminAdvanced', project=project)
    self.page_class._CheckForMovedProject(mr, request)

    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/adminAdvanced?ts=123234', project=project)
    self.page_class._CheckForMovedProject(mr, request)

    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/adminAdvanced.do', project=project)
    self.page_class._CheckForMovedProject(mr, request)

  def testGatherHelpData(self):
    help_data = self.page_class.GatherHelpData('fake mr', {})
    self.assertEqual(None, help_data['cue'])

  def testGatherDebugData_Visibility(self):
    project = fake.Project(
        project_name='testtest', state=project_pb2.ProjectState.LIVE)
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/foo/servlet_path', project=project)
    debug_data = self.page_class.GatherDebugData(mr, {})
    self.assertEqual('off', debug_data['dbg'])

    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/foo/servlet_path?debug=1', project=project)
    debug_data = self.page_class.GatherDebugData(mr, {})
    self.assertEqual('on', debug_data['dbg'])


class ProjectIsRestrictedTest(unittest.TestCase):

  def testNonRestrictedProject(self):
    proj = project_pb2.Project()
    mr = testing_helpers.MakeMonorailRequest()
    mr.project = proj

    proj.access = project_pb2.ProjectAccess.ANYONE
    proj.state = project_pb2.ProjectState.LIVE
    self.assertFalse(servlet._ProjectIsRestricted(mr))

    proj.state = project_pb2.ProjectState.ARCHIVED
    self.assertFalse(servlet._ProjectIsRestricted(mr))

  def testRestrictedProject(self):
    proj = project_pb2.Project()
    mr = testing_helpers.MakeMonorailRequest()
    mr.project = proj

    proj.state = project_pb2.ProjectState.LIVE
    proj.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    self.assertTrue(servlet._ProjectIsRestricted(mr))


FORM_URL = 'http://example.com/issues/form.php'


class ComputeIssueEntryURLTest(unittest.TestCase):

  def setUp(self):
    self.project = project_pb2.Project()
    self.project.project_name = 'proj'
    self.config = tracker_pb2.ProjectIssueConfig()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def testComputeIssueEntryURL_Normal(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/detail?id=123&q=term',
        project=self.project)

    url = servlet._ComputeIssueEntryURL(mr, self.config)
    self.assertEqual('entry', url)

  def testComputeIssueEntryURL_Customized(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/issues/detail?id=123&q=term',
        project=self.project)
    mr.auth.user_id = 111L
    self.config.custom_issue_entry_url = FORM_URL

    url = servlet._ComputeIssueEntryURL(mr, self.config)
    self.assertTrue(url.startswith(FORM_URL))
    self.assertIn('token=', url)
    self.assertIn('role=', url)
    self.assertIn('continue=', url)


if __name__ == '__main__':
  unittest.main()
