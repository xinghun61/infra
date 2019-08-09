# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the framework_helpers module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import unittest

import mox
import time

from businesslogic import work_env
from framework import framework_helpers
from framework import framework_views
from proto import features_pb2
from proto import project_pb2
from proto import user_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class HelperFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.time = self.mox.CreateMock(framework_helpers.time)
    framework_helpers.time = self.time  # Point to a mocked out time module.

  def tearDown(self):
    framework_helpers.time = time  # Point back to the time module.
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testRetryDecorator_ExceedFailures(self):
    class Tracker(object):
      func_called = 0
    tracker = Tracker()

    # Use a function that always fails.
    @framework_helpers.retry(2, delay=1, backoff=2)
    def testFunc(tracker):
      tracker.func_called += 1
      raise Exception('Failed')

    self.time.sleep(1).AndReturn(None)
    self.time.sleep(2).AndReturn(None)
    self.mox.ReplayAll()
    with self.assertRaises(Exception):
      testFunc(tracker)
    self.mox.VerifyAll()
    self.assertEquals(3, tracker.func_called)

  def testRetryDecorator_EventuallySucceed(self):
    class Tracker(object):
      func_called = 0
    tracker = Tracker()

    # Use a function that succeeds on the 2nd attempt.
    @framework_helpers.retry(2, delay=1, backoff=2)
    def testFunc(tracker):
      tracker.func_called += 1
      if tracker.func_called < 2:
        raise Exception('Failed')

    self.time.sleep(1).AndReturn(None)
    self.mox.ReplayAll()
    testFunc(tracker)
    self.mox.VerifyAll()
    self.assertEquals(2, tracker.func_called)

  def testGetRoleName(self):
    proj = project_pb2.Project()
    proj.owner_ids.append(111)
    proj.committer_ids.append(222)
    proj.contributor_ids.append(333)

    self.assertEquals(None, framework_helpers.GetRoleName(set(), proj))

    self.assertEquals(
        'Owner', framework_helpers.GetRoleName({111}, proj))
    self.assertEquals(
        'Committer', framework_helpers.GetRoleName({222}, proj))
    self.assertEquals(
        'Contributor', framework_helpers.GetRoleName({333}, proj))

    self.assertEquals(
        'Owner',
        framework_helpers.GetRoleName({111, 222, 999}, proj))
    self.assertEquals(
        'Committer',
        framework_helpers.GetRoleName({222, 333, 999}, proj))
    self.assertEquals(
        'Contributor',
        framework_helpers.GetRoleName({333, 999}, proj))

  def testGetHotlistRoleName(self):
    hotlist = features_pb2.Hotlist()
    hotlist.owner_ids.append(111)
    hotlist.editor_ids.append(222)
    hotlist.follower_ids.append(333)

    self.assertEquals(None, framework_helpers.GetHotlistRoleName(
        set(), hotlist))

    self.assertEquals(
        'Owner', framework_helpers.GetHotlistRoleName({111}, hotlist))
    self.assertEquals(
        'Editor', framework_helpers.GetHotlistRoleName({222}, hotlist))
    self.assertEquals(
        'Follower', framework_helpers.GetHotlistRoleName({333}, hotlist))

    self.assertEquals(
        'Owner',
        framework_helpers.GetHotlistRoleName({111, 222, 999}, hotlist))
    self.assertEquals(
        'Editor',
        framework_helpers.GetHotlistRoleName({222, 333, 999}, hotlist))
    self.assertEquals(
        'Follower',
        framework_helpers.GetHotlistRoleName({333, 999}, hotlist))


class UrlFormattingTest(unittest.TestCase):
  """Tests for URL formatting."""

  def setUp(self):
    self.services = service_manager.Services(user=fake.UserService())

  def testFormatMovedProjectURL(self):
    """Project foo has been moved to bar.  User is visiting /p/foo/..."""
    mr = testing_helpers.MakeMonorailRequest()
    mr.current_page_url = '/p/foo/'
    self.assertEqual(
      '/p/bar/',
      framework_helpers.FormatMovedProjectURL(mr, 'bar'))

    mr.current_page_url = '/p/foo/issues/list'
    self.assertEqual(
      '/p/bar/issues/list',
      framework_helpers.FormatMovedProjectURL(mr, 'bar'))

    mr.current_page_url = '/p/foo/issues/detail?id=123'
    self.assertEqual(
      '/p/bar/issues/detail?id=123',
      framework_helpers.FormatMovedProjectURL(mr, 'bar'))

    mr.current_page_url = '/p/foo/issues/detail?id=123#c7'
    self.assertEqual(
      '/p/bar/issues/detail?id=123#c7',
      framework_helpers.FormatMovedProjectURL(mr, 'bar'))

  def testFormatCanonicalURL(self):
    mr = testing_helpers.MakeMonorailRequest(
      path='/dude/wheres/my/car?foo=bar',
      headers={'Host': 'example.com'})

    self.assertEqual(
      'http://example.com/dude/wheres/my/car?foo=bar',
      framework_helpers.FormatCanonicalURL(
        mr, ['bar', 'foo', 'baz']))

    self.assertEqual(
      'http://example.com/dude/wheres/my/car?foo=bar',
      framework_helpers.FormatCanonicalURL(
        mr, ['foo']))

    self.assertEqual(
      'http://example.com/dude/wheres/my/car',
      framework_helpers.FormatCanonicalURL(
        mr, []))

  def testFormatURL(self):
    mr = testing_helpers.MakeMonorailRequest()
    path = '/dude/wheres/my/car'
    recognized_params = [(name, mr.GetParam(name)) for name in
                         framework_helpers.RECOGNIZED_PARAMS]
    url = framework_helpers.FormatURL(recognized_params, path)
    self.assertEqual(path, url)

  def testFormatURLWithRecognizedParams(self):
    params = {}
    query = []
    for name in framework_helpers.RECOGNIZED_PARAMS:
      params[name] = name
      query.append('%s=%s' % (name, 123))
    path = '/dude/wheres/my/car'
    expected = '%s?%s' % (path, '&'.join(query))
    mr = testing_helpers.MakeMonorailRequest(path=expected)
    recognized_params = [(name, mr.GetParam(name)) for name in
                         framework_helpers.RECOGNIZED_PARAMS]
    # No added params.
    url = framework_helpers.FormatURL(recognized_params, path)
    self.assertEqual(expected, url)

  def testFormatURLWithKeywordArgs(self):
    params = {}
    query_pairs = []
    for name in framework_helpers.RECOGNIZED_PARAMS:
      params[name] = name
      if name != 'can' and name != 'start':
        query_pairs.append('%s=%s' % (name, 123))
    path = '/dude/wheres/my/car'
    mr = testing_helpers.MakeMonorailRequest(
        path='%s?%s' % (path, '&'.join(query_pairs)))
    query_pairs.append('can=yep')
    query_pairs.append('start=486')
    query_string = '&'.join(query_pairs)
    expected = '%s?%s' % (path, query_string)
    recognized_params = [(name, mr.GetParam(name)) for name in
                         framework_helpers.RECOGNIZED_PARAMS]
    url = framework_helpers.FormatURL(
        recognized_params, path, can='yep', start=486)
    self.assertEqual(expected, url)

  def testFormatURLWithKeywordArgsAndID(self):
    params = {}
    query_pairs = []
    query_pairs.append('id=200')  # id should be the first parameter.
    for name in framework_helpers.RECOGNIZED_PARAMS:
      params[name] = name
      if name != 'can' and name != 'start':
        query_pairs.append('%s=%s' % (name, 123))
    path = '/dude/wheres/my/car'
    mr = testing_helpers.MakeMonorailRequest(
        path='%s?%s' % (path, '&'.join(query_pairs)))
    query_pairs.append('can=yep')
    query_pairs.append('start=486')
    query_string = '&'.join(query_pairs)
    expected = '%s?%s' % (path, query_string)
    recognized_params = [(name, mr.GetParam(name)) for name in
                         framework_helpers.RECOGNIZED_PARAMS]
    url = framework_helpers.FormatURL(
        recognized_params, path, can='yep', start=486, id=200)
    self.assertEqual(expected, url)

  def testFormatURLWithStrangeParams(self):
    mr = testing_helpers.MakeMonorailRequest(path='/foo?start=0')
    recognized_params = [(name, mr.GetParam(name)) for name in
                         framework_helpers.RECOGNIZED_PARAMS]
    url = framework_helpers.FormatURL(
        recognized_params, '/foo',
        r=0, path='/foo/bar', sketchy='/foo/ bar baz ')
    self.assertEqual(
        '/foo?start=0&path=/foo/bar&r=0&sketchy=/foo/%20bar%20baz%20',
        url)

  def testFormatAbsoluteURL(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/some-path',
        headers={'Host': 'www.test.com'})
    self.assertEqual(
        'http://www.test.com/p/proj/some/path',
        framework_helpers.FormatAbsoluteURL(mr, '/some/path'))

  def testFormatAbsoluteURL_CommonRequestParams(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/some-path?foo=bar&can=1',
        headers={'Host': 'www.test.com'})
    self.assertEqual(
        'http://www.test.com/p/proj/some/path?can=1',
        framework_helpers.FormatAbsoluteURL(mr, '/some/path'))
    self.assertEqual(
        'http://www.test.com/p/proj/some/path',
        framework_helpers.FormatAbsoluteURL(
            mr, '/some/path', copy_params=False))

  def testFormatAbsoluteURL_NoProject(self):
    path = '/some/path'
    _request, mr = testing_helpers.GetRequestObjects(
        headers={'Host': 'www.test.com'}, path=path)
    url = framework_helpers.FormatAbsoluteURL(mr, path, include_project=False)
    self.assertEqual(url, 'http://www.test.com/some/path')

  def testGetHostPort_Local(self):
    """We use testing-app.appspot.com when running locally."""
    self.assertEqual('testing-app.appspot.com',
                     framework_helpers.GetHostPort())
    self.assertEqual('testing-app.appspot.com',
                     framework_helpers.GetHostPort(project_name='proj'))

  @mock.patch('settings.preferred_domains',
              {'testing-app.appspot.com': 'example.com'})
  def testGetHostPort_PreferredDomain(self):
    """A prod server can have a preferred domain."""
    self.assertEqual('example.com',
                     framework_helpers.GetHostPort())
    self.assertEqual('example.com',
                     framework_helpers.GetHostPort(project_name='proj'))

  @mock.patch('settings.branded_domains',
              {'proj': 'branded.com', '*': 'unbranded.com'})
  @mock.patch('settings.preferred_domains',
              {'testing-app.appspot.com': 'example.com'})
  def testGetHostPort_BrandedDomain(self):
    """A prod server can have a preferred domain."""
    self.assertEqual('example.com',
                     framework_helpers.GetHostPort())
    self.assertEqual('branded.com',
                     framework_helpers.GetHostPort(project_name='proj'))
    self.assertEqual('unbranded.com',
                     framework_helpers.GetHostPort(project_name='other-proj'))

  def testIssueCommentURL(self):
    hostport = 'port.someplex.com'
    proj = project_pb2.Project()
    proj.project_name = 'proj'

    url = 'https://port.someplex.com/p/proj/issues/detail?id=2'
    actual_url = framework_helpers.IssueCommentURL(
        hostport, proj, 2)
    self.assertEqual(actual_url, url)

    url = 'https://port.someplex.com/p/proj/issues/detail?id=2#c2'
    actual_url = framework_helpers.IssueCommentURL(
        hostport, proj, 2, seq_num=2)
    self.assertEqual(actual_url, url)


class WordWrapSuperLongLinesTest(unittest.TestCase):

  def testEmptyLogMessage(self):
    msg = ''
    wrapped_msg = framework_helpers.WordWrapSuperLongLines(msg)
    self.assertEqual(wrapped_msg, '')

  def testShortLines(self):
    msg = 'one\ntwo\nthree\n'
    wrapped_msg = framework_helpers.WordWrapSuperLongLines(msg)
    expected = 'one\ntwo\nthree\n'
    self.assertEqual(wrapped_msg, expected)

  def testOneLongLine(self):
    msg = ('This is a super long line that just goes on and on '
           'and it seems like it will never stop because it is '
           'super long and it was entered by a user who had no '
           'familiarity with the return key.')
    wrapped_msg = framework_helpers.WordWrapSuperLongLines(msg)
    expected = ('This is a super long line that just goes on and on and it '
                'seems like it will never stop because it\n'
                'is super long and it was entered by a user who had no '
                'familiarity with the return key.')
    self.assertEqual(wrapped_msg, expected)

    msg2 = ('This is a super long line that just goes on and on '
            'and it seems like it will never stop because it is '
            'super long and it was entered by a user who had no '
            'familiarity with the return key. '
            'This is a super long line that just goes on and on '
            'and it seems like it will never stop because it is '
            'super long and it was entered by a user who had no '
            'familiarity with the return key.')
    wrapped_msg2 = framework_helpers.WordWrapSuperLongLines(msg2)
    expected2 = ('This is a super long line that just goes on and on and it '
                 'seems like it will never stop because it\n'
                 'is super long and it was entered by a user who had no '
                 'familiarity with the return key. This is a\n'
                 'super long line that just goes on and on and it seems like '
                 'it will never stop because it is super\n'
                 'long and it was entered by a user who had no familiarity '
                 'with the return key.')
    self.assertEqual(wrapped_msg2, expected2)

  def testMixOfShortAndLong(self):
    msg = ('[Author: mpcomplete]\n'
           '\n'
           # Description on one long line
           'Fix a memory leak in JsArray and JsObject for the IE and NPAPI '
           'ports.  Each time you call GetElement* or GetProperty* to '
           'retrieve string or object token, the token would be leaked.  '
           'I added a JsScopedToken to ensure that the right thing is '
           'done when the object leaves scope, depending on the platform.\n'
           '\n'
           'R=zork\n'
           'CC=google-gears-eng@googlegroups.com\n'
           'DELTA=108  (52 added, 36 deleted, 20 changed)\n'
           'OCL=5932446\n'
           'SCL=5933728\n')
    wrapped_msg = framework_helpers.WordWrapSuperLongLines(msg)
    expected = (
        '[Author: mpcomplete]\n'
        '\n'
        'Fix a memory leak in JsArray and JsObject for the IE and NPAPI '
        'ports.  Each time you call\n'
        'GetElement* or GetProperty* to retrieve string or object token, the '
        'token would be leaked.  I added\n'
        'a JsScopedToken to ensure that the right thing is done when the '
        'object leaves scope, depending on\n'
        'the platform.\n'
        '\n'
        'R=zork\n'
        'CC=google-gears-eng@googlegroups.com\n'
        'DELTA=108  (52 added, 36 deleted, 20 changed)\n'
        'OCL=5932446\n'
        'SCL=5933728\n')
    self.assertEqual(wrapped_msg, expected)


class ComputeListDeltasTest(unittest.TestCase):

  def DoOne(self, old=None, new=None, added=None, removed=None):
    """Run one call to the target method and check expected results."""
    actual_added, actual_removed = framework_helpers.ComputeListDeltas(
        old, new)
    self.assertItemsEqual(added, actual_added)
    self.assertItemsEqual(removed, actual_removed)

  def testEmptyLists(self):
    self.DoOne(old=[], new=[], added=[], removed=[])
    self.DoOne(old=[1, 2], new=[], added=[], removed=[1, 2])
    self.DoOne(old=[], new=[1, 2], added=[1, 2], removed=[])

  def testUnchanged(self):
    self.DoOne(old=[1], new=[1], added=[], removed=[])
    self.DoOne(old=[1, 2], new=[1, 2], added=[], removed=[])
    self.DoOne(old=[1, 2], new=[2, 1], added=[], removed=[])

  def testCompleteChange(self):
    self.DoOne(old=[1, 2], new=[3, 4], added=[3, 4], removed=[1, 2])

  def testGeneralChange(self):
    self.DoOne(old=[1, 2], new=[2], added=[], removed=[1])
    self.DoOne(old=[1], new=[1, 2], added=[2], removed=[])
    self.DoOne(old=[1, 2], new=[2, 3], added=[3], removed=[1])


class UserSettingsTest(unittest.TestCase):

  def setUp(self):
    self.mr = testing_helpers.MakeMonorailRequest()
    self.cnxn = 'cnxn'
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService())

  def testGatherUnifiedSettingsPageData(self):
    mr = self.mr
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    mr.auth.user_view.profile_url = '/u/profile/url'
    userprefs = user_pb2.UserPrefs(
      prefs=[user_pb2.UserPrefValue(name='public_issue_notice', value='true')])
    page_data = framework_helpers.UserSettings.GatherUnifiedSettingsPageData(
        mr.auth.user_id, mr.auth.user_view, mr.auth.user_pb, userprefs)

    expected_keys = [
        'settings_user',
        'settings_user_pb',
        'settings_user_is_banned',
        'self',
        'profile_url_fragment',
        'preview_on_hover',
        'settings_user_prefs',
        ]
    self.assertItemsEqual(expected_keys, list(page_data.keys()))

    self.assertEqual('profile/url', page_data['profile_url_fragment'])
    self.assertTrue(page_data['settings_user_prefs'].public_issue_notice)
    self.assertFalse(page_data['settings_user_prefs'].restrict_new_issues)

  def testGatherUnifiedSettingsPageData_NoUserPrefs(self):
    """If UserPrefs were not loaded, consider them all false."""
    mr = self.mr
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    userprefs = None

    page_data = framework_helpers.UserSettings.GatherUnifiedSettingsPageData(
        mr.auth.user_id, mr.auth.user_view, mr.auth.user_pb, userprefs)

    self.assertFalse(page_data['settings_user_prefs'].public_issue_notice)
    self.assertFalse(page_data['settings_user_prefs'].restrict_new_issues)

  def testProcessBanForm(self):
    """We can ban and unban users."""
    user = self.services.user.TestAddUser('one@example.com', 111)
    post_data = {'banned': 1, 'banned_reason': 'rude'}
    framework_helpers.UserSettings.ProcessBanForm(
      self.cnxn, self.services.user, post_data, 111, user)
    self.assertEqual('rude', user.banned)

    post_data = {}  # not banned
    framework_helpers.UserSettings.ProcessBanForm(
      self.cnxn, self.services.user, post_data, 111, user)
    self.assertEqual('', user.banned)

  def testProcessSettingsForm_OldStylePrefs(self):
    """We can set prefs that are stored in the User PB."""
    user = self.services.user.TestAddUser('one@example.com', 111)
    post_data = {'obscure_email': 1, 'notify': 1}
    with work_env.WorkEnv(self.mr, self.services) as we:
      framework_helpers.UserSettings.ProcessSettingsForm(
          we, post_data, user)

    self.assertTrue(user.obscure_email)
    self.assertTrue(user.notify_issue_change)
    self.assertFalse(user.notify_starred_ping)

  def testProcessSettingsForm_NewStylePrefs(self):
    """We can set prefs that are stored in the UserPrefs PB."""
    user = self.services.user.TestAddUser('one@example.com', 111)
    post_data = {'restrict_new_issues': 1}
    with work_env.WorkEnv(self.mr, self.services) as we:
      framework_helpers.UserSettings.ProcessSettingsForm(
          we, post_data, user)
      userprefs = we.GetUserPrefs(111)

    actual = {upv.name: upv.value
              for upv in userprefs.prefs}
    expected = {
      'restrict_new_issues': 'true',
      'public_issue_notice': 'false',
      }
    self.assertEqual(expected, actual)


class MurmurHash3Test(unittest.TestCase):

  def testMurmurHash(self):
    test_data = [
        ('', 0),
        ('agable@chromium.org', 4092810879),
        (u'jrobbins@chromium.org', 904770043),
        ('seanmccullough%google.com@gtempaccount.com', 1301269279),
        ('rmistry+monorail@chromium.org', 4186878788),
        ('jparent+foo@', 2923900874),
        ('@example.com', 3043483168),
    ]
    hashes = [framework_helpers.MurmurHash3_x86_32(x)
              for (x, _) in test_data]
    self.assertListEqual(hashes, [e for (_, e) in test_data])

  def testMurmurHashWithSeed(self):
    test_data = [
        ('', 1113155926, 2270882445),
        ('agable@chromium.org', 772936925, 3995066671),
        (u'jrobbins@chromium.org', 1519359761, 1273489513),
        ('seanmccullough%google.com@gtempaccount.com', 49913829, 1202521153),
        ('rmistry+monorail@chromium.org', 314860298, 3636123309),
        ('jparent+foo@', 195791379, 332453977),
        ('@example.com', 521490555, 257496459),
    ]
    hashes = [framework_helpers.MurmurHash3_x86_32(x, s)
              for (x, s, _) in test_data]
    self.assertListEqual(hashes, [e for (_, _, e) in test_data])


class MakeRandomKeyTest(unittest.TestCase):

  def testMakeRandomKey_Normal(self):
    key1 = framework_helpers.MakeRandomKey()
    key2 = framework_helpers.MakeRandomKey()
    self.assertEqual(128, len(key1))
    self.assertEqual(128, len(key2))
    self.assertNotEqual(key1, key2)

  def testMakeRandomKey_Length(self):
    key = framework_helpers.MakeRandomKey()
    self.assertEqual(128, len(key))
    key16 = framework_helpers.MakeRandomKey(length=16)
    self.assertEqual(16, len(key16))

  def testMakeRandomKey_Chars(self):
    key = framework_helpers.MakeRandomKey(chars='a', length=4)
    self.assertEqual('aaaa', key)


class IsServiceAccountTest(unittest.TestCase):

  def testIsServiceAccount(self):
    appspot = 'abc@appspot.gserviceaccount.com'
    developer = '@developer.gserviceaccount.com'
    bugdroid = 'bugdroid1@chromium.org'
    user = 'test@example.com'

    self.assertTrue(framework_helpers.IsServiceAccount(appspot))
    self.assertTrue(framework_helpers.IsServiceAccount(developer))
    self.assertTrue(framework_helpers.IsServiceAccount(bugdroid))
    self.assertFalse(framework_helpers.IsServiceAccount(user))

    client_emails = set([appspot, developer, bugdroid])
    self.assertTrue(framework_helpers.IsServiceAccount(
        appspot, client_emails=client_emails))
    self.assertTrue(framework_helpers.IsServiceAccount(
        developer, client_emails=client_emails))
    self.assertTrue(framework_helpers.IsServiceAccount(
        bugdroid, client_emails=client_emails))
    self.assertFalse(framework_helpers.IsServiceAccount(
        user, client_emails=client_emails))
