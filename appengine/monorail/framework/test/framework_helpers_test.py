# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the framework_helpers module."""

import unittest

import mox
import time

from framework import framework_helpers
from framework import framework_views
from proto import features_pb2
from proto import project_pb2
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
    proj.owner_ids.append(111L)
    proj.committer_ids.append(222L)
    proj.contributor_ids.append(333L)

    self.assertEquals(None, framework_helpers.GetRoleName(set(), proj))

    self.assertEquals(
        'Owner', framework_helpers.GetRoleName({111L}, proj))
    self.assertEquals(
        'Committer', framework_helpers.GetRoleName({222L}, proj))
    self.assertEquals(
        'Contributor', framework_helpers.GetRoleName({333L}, proj))

    self.assertEquals(
        'Owner',
        framework_helpers.GetRoleName({111L, 222L, 999L}, proj))
    self.assertEquals(
        'Committer',
        framework_helpers.GetRoleName({222L, 333L, 999L}, proj))
    self.assertEquals(
        'Contributor',
        framework_helpers.GetRoleName({333L, 999L}, proj))

  def testGetHotlistRoleName(self):
    hotlist = features_pb2.Hotlist()
    hotlist.owner_ids.append(111L)
    hotlist.editor_ids.append(222L)
    hotlist.follower_ids.append(333L)

    self.assertEquals(None, framework_helpers.GetHotlistRoleName(
        set(), hotlist))

    self.assertEquals(
        'Owner', framework_helpers.GetHotlistRoleName({111L}, hotlist))
    self.assertEquals(
        'Editor', framework_helpers.GetHotlistRoleName({222L}, hotlist))
    self.assertEquals(
        'Follower', framework_helpers.GetHotlistRoleName({333L}, hotlist))

    self.assertEquals(
        'Owner',
        framework_helpers.GetHotlistRoleName({111L, 222L, 999L}, hotlist))
    self.assertEquals(
        'Editor',
        framework_helpers.GetHotlistRoleName({222L, 333L, 999L}, hotlist))
    self.assertEquals(
        'Follower',
        framework_helpers.GetHotlistRoleName({333L, 999L}, hotlist))


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

  def testFormatURL(self):
    mr = testing_helpers.MakeMonorailRequest()
    path = '/dude/wheres/my/car'
    url = framework_helpers.FormatURL(mr, path)
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
    url = framework_helpers.FormatURL(mr, path)  # No added params.
    self.assertEqual(expected, url)

  def testFormatURLWithKeywordArgs(self):
    params = {}
    query_pairs = []
    for name in framework_helpers.RECOGNIZED_PARAMS:
      params[name] = name
      if name is not 'can' and name is not 'start':
        query_pairs.append('%s=%s' % (name, 123))
    path = '/dude/wheres/my/car'
    mr = testing_helpers.MakeMonorailRequest(
        path='%s?%s' % (path, '&'.join(query_pairs)))
    query_pairs.append('can=yep')
    query_pairs.append('start=486')
    query_string = '&'.join(query_pairs)
    expected = '%s?%s' % (path, query_string)
    url = framework_helpers.FormatURL(mr, path, can='yep', start=486)
    self.assertEqual(expected, url)

  def testFormatURLWithKeywordArgsAndID(self):
    params = {}
    query_pairs = []
    query_pairs.append('id=200')  # id should be the first parameter.
    for name in framework_helpers.RECOGNIZED_PARAMS:
      params[name] = name
      if name is not 'can' and name is not 'start':
        query_pairs.append('%s=%s' % (name, 123))
    path = '/dude/wheres/my/car'
    mr = testing_helpers.MakeMonorailRequest(
        path='%s?%s' % (path, '&'.join(query_pairs)))
    query_pairs.append('can=yep')
    query_pairs.append('start=486')
    query_string = '&'.join(query_pairs)
    expected = '%s?%s' % (path, query_string)
    url = framework_helpers.FormatURL(mr, path, can='yep', start=486, id=200)
    self.assertEqual(expected, url)

  def testFormatURLWithStrangeParams(self):
    mr = testing_helpers.MakeMonorailRequest(path='/foo?start=0')
    url = framework_helpers.FormatURL(
        mr, '/foo', r=0, path='/foo/bar', sketchy='/foo/ bar baz ')
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

  def testGatherUnifiedSettingsPageData(self):
    mr = testing_helpers.MakeMonorailRequest()
    mr.auth.user_view = framework_views.StuffUserView(100, 'user@invalid', True)
    mr.auth.user_view.profile_url = '/u/profile/url'
    page_data = framework_helpers.UserSettings.GatherUnifiedSettingsPageData(
        mr.auth.user_id, mr.auth.user_view, mr.auth.user_pb)

    expected_keys = [
        'api_request_reset',
        'api_request_lifetime_limit',
        'api_request_hard_limit',
        'api_request_soft_limit',
        'settings_user',
        'settings_user_pb',
        'settings_user_is_banned',
        'settings_user_ignore_action_limits',
        'self',
        'project_creation_reset',
        'issue_comment_reset',
        'issue_attachment_reset',
        'issue_bulk_edit_reset',
        'project_creation_lifetime_limit',
        'project_creation_soft_limit',
        'project_creation_hard_limit',
        'issue_comment_lifetime_limit',
        'issue_comment_soft_limit',
        'issue_comment_hard_limit',
        'issue_attachment_lifetime_limit',
        'issue_attachment_soft_limit',
        'issue_attachment_hard_limit',
        'issue_bulk_edit_lifetime_limit',
        'issue_bulk_edit_hard_limit',
        'issue_bulk_edit_soft_limit',
        'profile_url_fragment',
        'preview_on_hover',
        ]
    self.assertItemsEqual(expected_keys, page_data.keys())

    self.assertEqual('profile/url', page_data['profile_url_fragment'])
    # TODO(jrobbins): Test action limit support

  # TODO(jrobbins): Test ProcessForm.


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
