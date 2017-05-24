# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for issue tracker views."""

import unittest

import mox

from google.appengine.api import app_identity
from third_party import ezt

from framework import framework_views
from framework import gcs_helpers
from framework import urls
from proto import project_pb2
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj
from tracker import tracker_views


def _Issue(project_name, local_id, summary, status):
  issue = tracker_pb2.Issue()
  issue.project_name = project_name
  issue.local_id = local_id
  issue.issue_id = 100000 + local_id
  issue.summary = summary
  issue.status = status
  return issue


def _MakeConfig():
  config = tracker_pb2.ProjectIssueConfig()
  config.well_known_statuses.append(tracker_pb2.StatusDef(
      status='New', means_open=True))
  config.well_known_statuses.append(tracker_pb2.StatusDef(
      status='Old', means_open=False))
  return config


class IssueViewTest(unittest.TestCase):

  def setUp(self):
    self.issue1 = _Issue('proj', 1, 'not too long summary', 'New')
    self.issue2 = _Issue('proj', 2, 'sum 2', '')
    self.issue3 = _Issue('proj', 3, 'sum 3', '')
    self.issue4 = _Issue('proj', 4, 'sum 4', '')

    self.issue1.reporter_id = 1002
    self.issue1.owner_id = 2002
    self.issue1.labels.extend(['A', 'B'])
    self.issue1.derived_labels.extend(['C', 'D'])

    self.issue2.reporter_id = 2002
    self.issue2.labels.extend(['foo', 'bar'])
    self.issue2.blocked_on_iids.extend(
        [self.issue1.issue_id, self.issue3.issue_id])
    self.issue2.blocking_iids.extend(
        [self.issue1.issue_id, self.issue4.issue_id])
    dref = tracker_pb2.DanglingIssueRef()
    dref.project = 'codesite'
    dref.issue_id = 5001
    self.issue2.dangling_blocking_refs.append(dref)

    self.issue3.reporter_id = 3002
    self.issue3.labels.extend(['Hot'])

    self.issue4.reporter_id = 3002
    self.issue4.labels.extend(['Foo', 'Bar'])

    self.restricted = _Issue('proj', 7, 'summary 7', '')
    self.restricted.labels.extend([
        'Restrict-View-Commit', 'Restrict-View-MyCustomPerm'])
    self.restricted.derived_labels.extend([
        'Restrict-AddIssueComment-Commit', 'Restrict-EditIssue-Commit',
        'Restrict-Action-NeededPerm'])

    self.users_by_id = {
        0: 'user 0',
        1002: 'user 1002',
        2002: 'user 2002',
        3002: 'user 3002',
        4002: 'user 4002',
        }

  def CheckSimpleIssueView(self, config):
    view1 = tracker_views.IssueView(
        self.issue1, self.users_by_id, config)
    self.assertEqual('not too long summary', view1.summary)
    self.assertEqual('New', view1.status.name)
    self.assertEqual('user 2002', view1.owner)
    self.assertEqual('A', view1.labels[0].name)
    self.assertEqual('B', view1.labels[1].name)
    self.assertEqual('C', view1.derived_labels[0].name)
    self.assertEqual('D', view1.derived_labels[1].name)
    self.assertEqual([], view1.blocked_on)
    self.assertEqual([], view1.blocking)
    detail_url = '/p/%s%s?id=%d' % (
        self.issue1.project_name, urls.ISSUE_DETAIL,
        self.issue1.local_id)
    self.assertEqual(detail_url, view1.detail_relative_url)
    return view1

  def testSimpleIssueView(self):
    config = tracker_pb2.ProjectIssueConfig()
    view1 = self.CheckSimpleIssueView(config)
    self.assertEqual('', view1.status.docstring)

    config.well_known_statuses.append(tracker_pb2.StatusDef(
        status='New', status_docstring='Issue has not had review yet'))
    view1 = self.CheckSimpleIssueView(config)
    self.assertEqual('Issue has not had review yet',
                     view1.status.docstring)
    self.assertIsNone(view1.restrictions.has_restrictions)
    self.assertEqual('', view1.restrictions.view)
    self.assertEqual('', view1.restrictions.add_comment)
    self.assertEqual('', view1.restrictions.edit)

  def testIsOpen(self):
    config = _MakeConfig()
    view1 = tracker_views.IssueView(
        self.issue1, self.users_by_id, config)
    self.assertEqual(ezt.boolean(True), view1.is_open)

    self.issue1.status = 'Old'
    view1 = tracker_views.IssueView(
        self.issue1, self.users_by_id, config)
    self.assertEqual(ezt.boolean(False), view1.is_open)

  def testIssueViewWithBlocking(self):
    all_related={
        self.issue1.issue_id: self.issue1,
        self.issue2.issue_id: self.issue2,
        self.issue3.issue_id: self.issue3,
        self.issue4.issue_id: self.issue4,
        }
    # Treat issues 3 and 4 as visible to the current user.
    view2 = tracker_views.IssueView(
        self.issue2, self.users_by_id, _MakeConfig(),
        open_related={self.issue1.issue_id: self.issue1,
                      self.issue3.issue_id: self.issue3},
        closed_related={self.issue4.issue_id: self.issue4},
        all_related=all_related)
    self.assertEqual(['not too long summary', 'sum 3'],
                     [irv.summary for irv in view2.blocked_on])
    self.assertEqual(['not too long summary', 'sum 4',
                      'Issue 5001 in codesite.'],
                     [irv.summary for irv in view2.blocking])

    # Now, treat issues 3 and 4 as not visible to the current user.
    view2 = tracker_views.IssueView(
        self.issue2, self.users_by_id, _MakeConfig(),
        open_related={self.issue1.issue_id: self.issue1}, closed_related={},
        all_related=all_related)
    self.assertEqual(['not too long summary', None],
                     [irv.summary for irv in view2.blocked_on])
    self.assertEqual(['not too long summary', None, 'Issue 5001 in codesite.'],
                     [irv.summary for irv in view2.blocking])

    # Treat nothing as visible to the current user. Can still see dangling ref.
    view2 = tracker_views.IssueView(
        self.issue2, self.users_by_id, _MakeConfig(),
        open_related={}, closed_related={}, all_related=all_related)
    self.assertEqual([None, None],
                     [irv.summary for irv in view2.blocked_on])
    self.assertEqual([None, None, 'Issue 5001 in codesite.'],
                     [irv.summary for irv in view2.blocking])

  def testIssueViewWithRestrictions(self):
    view = tracker_views.IssueView(
        self.restricted, self.users_by_id, _MakeConfig())
    self.assertTrue(view.restrictions.has_restrictions)
    self.assertEqual('Commit and MyCustomPerm', view.restrictions.view)
    self.assertEqual('Commit', view.restrictions.add_comment)
    self.assertEqual('Commit', view.restrictions.edit)
    self.assertEqual(['Restrict-Action-NeededPerm'], view.restrictions.other)
    self.assertEqual('Restrict-View-Commit', view.labels[0].name)
    self.assertTrue(view.labels[0].is_restrict)


class RestrictionsViewTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class IssueRefViewTest(unittest.TestCase):

  issue1 = testing_helpers.Blank(
      issue_id=1,
      local_id=1,
      project_name='foo',
      summary='blue screen')
  issue2 = testing_helpers.Blank(
      issue_id=2,
      local_id=2,
      project_name='foo',
      summary='hissing noise')
  issue3 = testing_helpers.Blank(
      issue_id=3,
      local_id=3,
      project_name='foo',
      summary='sinking feeling')
  issue4 = testing_helpers.Blank(
      issue_id=4,
      local_id=4,
      project_name='bar',
      summary='aliens among us')

  def testNormalCase(self):
    open_list = {1: self.issue1,
                 2: self.issue2}
    closed_list = {3: self.issue3}

    irv = tracker_views.IssueRefView('foo', self.issue1, open_list, closed_list)
    self.assertEquals(irv.visible, ezt.boolean(True))
    self.assertEquals(irv.is_open, ezt.boolean(True))
    self.assertEquals(irv.url, 'detail?id=1')
    self.assertEquals(irv.display_name, 'issue 1')
    self.assertEquals(irv.summary, 'blue screen')

    irv = tracker_views.IssueRefView('foo', self.issue3, open_list, closed_list)
    self.assertEquals(irv.visible, ezt.boolean(True))
    self.assertEquals(irv.is_open, ezt.boolean(False))
    self.assertEquals(irv.url, 'detail?id=3')
    self.assertEquals(irv.display_name, 'issue 3')
    self.assertEquals(irv.summary, 'sinking feeling')

  def testMissingIssueShouldNotBeVisible(self):
    open_list = {1: self.issue1,
                 2: self.issue2}
    closed_list = {3: self.issue3}

    irv = tracker_views.IssueRefView('foo', None, open_list, closed_list)
    self.assertEquals(irv.visible, ezt.boolean(False))

  def testCrossProjectReference(self):
    open_list = {1: self.issue1,
                 2: self.issue2}
    closed_list = {3: self.issue3,
                   4: self.issue4}

    irv = tracker_views.IssueRefView('foo', self.issue4, open_list, closed_list)
    self.assertEquals(irv.visible, ezt.boolean(True))
    self.assertEquals(irv.is_open, ezt.boolean(False))
    self.assertEquals(
        irv.url, '/p/bar%s?id=4' % urls.ISSUE_DETAIL)
    self.assertEquals(irv.display_name, 'issue bar:4')
    self.assertEquals(irv.summary, 'aliens among us')


class DanglingIssueRefViewTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class AttachmentViewTest(unittest.TestCase):

  def MakeViewAndVerifyFields(
      self, size, name, mimetype, expected_size_str, expect_viewable):
    attach_pb = tracker_pb2.Attachment()
    attach_pb.filesize = size
    attach_pb.attachment_id = 12345
    attach_pb.filename = name
    attach_pb.mimetype = mimetype

    view = tracker_views.AttachmentView(attach_pb, 'proj')
    self.assertEqual('/images/paperclip.png', view.iconurl)
    self.assertEqual(expected_size_str, view.filesizestr)
    dl = 'attachment?aid=12345'
    self.assertEqual(dl, view.downloadurl)
    if expect_viewable:
      self.assertEqual(dl + '&inline=1', view.url)
      self.assertEqual(dl + '&inline=1&thumb=1', view.thumbnail_url)
    else:
      self.assertEqual(None, view.url)
      self.assertEqual(None, view.thumbnail_url)

  def testNonImage(self):
    self.MakeViewAndVerifyFields(
        123, 'file.ext', 'funky/bits', '123 bytes', False)

  def testViewableImage(self):
    self.MakeViewAndVerifyFields(
        123, 'logo.gif', 'image/gif', '123 bytes', True)

    self.MakeViewAndVerifyFields(
        123, 'screenshot.jpg', 'image/jpeg', '123 bytes', True)

  def testHugeImage(self):
    self.MakeViewAndVerifyFields(
        18 * 1024 * 1024, 'panorama.png', 'image/jpeg', '18.0 MB', False)

  def testViewableText(self):
    name = 'hello.c'
    attach_pb = tracker_pb2.Attachment()
    attach_pb.filesize = 1234
    attach_pb.attachment_id = 12345
    attach_pb.filename = name
    attach_pb.mimetype = 'text/plain'
    view = tracker_views.AttachmentView(attach_pb, 'proj')

    view_url = '/p/proj/issues/attachmentText?aid=12345'
    self.assertEqual(view_url, view.url)


class LogoViewTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testProjectWithLogo(self):
    bucket_name = 'testbucket'
    logo_gcs_id = '123'
    logo_file_name = 'logo.png'
    project_pb = project_pb2.MakeProject(
        'testProject', logo_gcs_id=logo_gcs_id, logo_file_name=logo_file_name)
    object_path = '/' + bucket_name + logo_gcs_id

    self.mox.StubOutWithMock(app_identity, 'get_default_gcs_bucket_name')
    app_identity.get_default_gcs_bucket_name().AndReturn(bucket_name)

    self.mox.StubOutWithMock(gcs_helpers, 'SignUrl')
    gcs_helpers.SignUrl(object_path + '-thumbnail').AndReturn('signed/url')
    gcs_helpers.SignUrl(object_path).AndReturn('signed/url')

    self.mox.ReplayAll()

    view = tracker_views.LogoView(project_pb)
    self.mox.VerifyAll()
    self.assertEquals('logo.png', view.filename)
    self.assertEquals('image/png', view.mimetype)
    self.assertEquals('signed/url', view.thumbnail_url)
    self.assertEquals('signed/url&response-content-displacement=attachment%3B'
                      '+filename%3Dlogo.png', view.viewurl)

  def testProjectWithNoLogo(self):
    project_pb = project_pb2.MakeProject('testProject')
    view = tracker_views.LogoView(project_pb)
    self.assertEquals('', view.thumbnail_url)
    self.assertEquals('', view.viewurl)


class IsViewableImageTest(unittest.TestCase):

  def testIsViewableImage(self):
    self.assertTrue(tracker_views.IsViewableImage('image/gif', 123))
    self.assertTrue(tracker_views.IsViewableImage(
        'image/gif; charset=binary', 123))
    self.assertTrue(tracker_views.IsViewableImage('image/png', 123))
    self.assertTrue(tracker_views.IsViewableImage(
        'image/png; charset=binary', 123))
    self.assertTrue(tracker_views.IsViewableImage('image/x-png', 123))
    self.assertTrue(tracker_views.IsViewableImage('image/jpeg', 123))
    self.assertTrue(tracker_views.IsViewableImage(
        'image/jpeg; charset=binary', 123))
    self.assertTrue(tracker_views.IsViewableImage(
        'image/jpeg', 14 * 1024 * 1024))

    self.assertFalse(tracker_views.IsViewableImage('junk/bits', 123))
    self.assertFalse(tracker_views.IsViewableImage(
        'junk/bits; charset=binary', 123))
    self.assertFalse(tracker_views.IsViewableImage(
        'image/jpeg', 16 * 1024 * 1024))


class IsViewableVideoTest(unittest.TestCase):

  def testIsViewableVideo(self):
    self.assertTrue(tracker_views.IsViewableVideo('video/ogg', 123))
    self.assertTrue(tracker_views.IsViewableVideo(
        'video/ogg; charset=binary', 123))
    self.assertTrue(tracker_views.IsViewableVideo('video/mp4', 123))
    self.assertTrue(tracker_views.IsViewableVideo(
        'video/mp4; charset=binary', 123))
    self.assertTrue(tracker_views.IsViewableVideo('video/mpg', 123))
    self.assertTrue(tracker_views.IsViewableVideo(
        'video/mpg; charset=binary', 123))
    self.assertTrue(tracker_views.IsViewableVideo('video/mpeg', 123))
    self.assertTrue(tracker_views.IsViewableVideo(
        'video/mpeg; charset=binary', 123))
    self.assertTrue(tracker_views.IsViewableVideo(
        'video/mpeg', 14 * 1024 * 1024))

    self.assertFalse(tracker_views.IsViewableVideo('junk/bits', 123))
    self.assertFalse(tracker_views.IsViewableVideo(
        'junk/bits; charset=binary', 123))
    self.assertFalse(tracker_views.IsViewableVideo(
        'video/mp4', 16 * 1024 * 1024))


class IsViewableTextTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class AmendmentViewTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class ComponentDefViewTest(unittest.TestCase):
  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        config=fake.ConfigService())
    self.services.user.TestAddUser('admin@example.com', 111L)
    self.services.user.TestAddUser('cc@example.com', 222L)
    self.users_by_id = framework_views.MakeAllUserViews(
      'cnxn', self.services.user, [111L, 222L])
    self.services.config.TestAddLabelsDict({'Hot': 1, 'Cold': 2})
    self.cd = tracker_bizobj.MakeComponentDef(
      10, 789, 'UI', 'User interface', False,
      [111L], [222L], 0, 111L, label_ids=[1, 2])

  def testRootComponent(self):
    view = tracker_views.ComponentDefView(
       'cnxn', self.services, self.cd, self.users_by_id)
    self.assertEquals('', view.parent_path)
    self.assertEquals('UI', view.leaf_name)
    self.assertEquals('User interface', view.docstring_short)
    self.assertEquals('admin@example.com', view.admins[0].email)
    self.assertEquals(['Hot', 'Cold'], view.labels)
    self.assertEquals('all toplevel active ', view.classes)

  def testNestedComponent(self):
    self.cd.path = 'UI>Dialogs>Print'
    view = tracker_views.ComponentDefView(
       'cnxn', self.services, self.cd, self.users_by_id)
    self.assertEquals('UI>Dialogs', view.parent_path)
    self.assertEquals('Print', view.leaf_name)
    self.assertEquals('User interface', view.docstring_short)
    self.assertEquals('admin@example.com', view.admins[0].email)
    self.assertEquals(['Hot', 'Cold'], view.labels)
    self.assertEquals('all active ', view.classes)


class ComponentValueTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class FieldValueViewTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests

class FieldValueViewTest_Applicability(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class MakeFieldValueViewTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class FindFieldValuesTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class MakeBounceFieldValueViewsTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class ConvertLabelsToFieldValuesTest(unittest.TestCase):

  def testConvertLabelsToFieldValues_NoLabels(self):
    result = tracker_views._ConvertLabelsToFieldValues(
        [], 'opsys', {})
    self.assertEqual([], result)

  def testConvertLabelsToFieldValues_NoMatch(self):
    result = tracker_views._ConvertLabelsToFieldValues(
        ['Pri-3', 'M-44', 'Security', 'Via-Wizard'], 'opsys', {})
    self.assertEqual([], result)

  def testConvertLabelsToFieldValues_HasMatch(self):
    result = tracker_views._ConvertLabelsToFieldValues(
        ['Pri-3', 'M-44', 'Security', 'OpSys-OSX'], 'opsys', {})
    self.assertEqual(1, len(result))
    self.assertEqual('OSX', result[0].val)
    self.assertEqual('OSX', result[0].val_short)
    self.assertEqual('', result[0].docstring)

    result = tracker_views._ConvertLabelsToFieldValues(
        ['Pri-3', 'M-44', 'Security', 'OpSys-OSX', 'OpSys-All'],
         'opsys', {'OpSys-All': 'Happens everywhere'})
    self.assertEqual(2, len(result))
    self.assertEqual('OSX', result[0].val)
    self.assertEqual('OSX', result[0].val_short)
    self.assertEqual('', result[0].docstring)
    self.assertEqual('All', result[1].val)
    self.assertEqual('All', result[1].val_short)
    self.assertEqual('Happens everywhere', result[1].docstring)


class FieldDefViewTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class IssueTemplateViewTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class MakeFieldUserViewsTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class ConfigViewTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests
