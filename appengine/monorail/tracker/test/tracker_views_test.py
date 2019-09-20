# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for issue tracker views."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import unittest

import mox

from google.appengine.api import app_identity
from third_party import ezt

from framework import framework_views
from framework import gcs_helpers
from framework import template_helpers
from framework import urls
from proto import project_pb2
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import attachment_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers
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
  config.well_known_labels = [
    tracker_pb2.LabelDef(
        label='Priority-High', label_docstring='Must be resolved'),
    tracker_pb2.LabelDef(
        label='Priority-Low', label_docstring='Can be slipped'),
    ]
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


class AttachmentViewTest(unittest.TestCase):

  def setUp(self):
    self.orig_sign_attachment_id = attachment_helpers.SignAttachmentID
    attachment_helpers.SignAttachmentID = (
        lambda aid: 'signed_%d' % aid)

  def tearDown(self):
    attachment_helpers.SignAttachmentID = self.orig_sign_attachment_id

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
    dl = 'attachment?aid=12345&signed_aid=signed_12345'
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

    self.mox.StubOutWithMock(app_identity, 'get_default_gcs_bucket_name')
    app_identity.get_default_gcs_bucket_name().AndReturn(bucket_name)

    self.mox.StubOutWithMock(gcs_helpers, 'SignUrl')
    gcs_helpers.SignUrl(bucket_name,
        logo_gcs_id + '-thumbnail').AndReturn('signed/url')
    gcs_helpers.SignUrl(bucket_name, logo_gcs_id).AndReturn('signed/url')

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


class AmendmentViewTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class ComponentDefViewTest(unittest.TestCase):
  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        config=fake.ConfigService())
    self.services.user.TestAddUser('admin@example.com', 111)
    self.services.user.TestAddUser('cc@example.com', 222)
    self.users_by_id = framework_views.MakeAllUserViews(
      'cnxn', self.services.user, [111, 222])
    self.services.config.TestAddLabelsDict({'Hot': 1, 'Cold': 2})
    self.cd = tracker_bizobj.MakeComponentDef(
      10, 789, 'UI', 'User interface', False,
      [111], [222], 0, 111, label_ids=[1, 2])

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

  def setUp(self):
    self.config = tracker_pb2.ProjectIssueConfig()
    self.estdays_fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'EstDays', tracker_pb2.FieldTypes.INT_TYPE, None,
        None, False, False, False, 3, 99, None, False, None, None,
        None, 'no_action', 'descriptive docstring', False, approval_id=None,
        is_phase_field=False)
    self.designdoc_fd = tracker_bizobj.MakeFieldDef(
        2, 789, 'DesignDoc', tracker_pb2.FieldTypes.STR_TYPE, 'Enhancement',
        None, False, False, False, None, None, None, False, None, None,
        None, 'no_action', 'descriptive docstring', False, approval_id=None,
        is_phase_field=False)
    self.mtarget_fd = tracker_bizobj.MakeFieldDef(
        3, 789, 'M-Target', tracker_pb2.FieldTypes.INT_TYPE, 'Enhancement',
        None, False, False, False, None, None, None, False, None, None,
        None, 'no_action', 'doc doc', False, approval_id=None,
        is_phase_field=True)
    self.config.field_defs = [self.estdays_fd, self.designdoc_fd]

  def testNoValues(self):
    """We can create a FieldValueView with no values."""
    values = []
    derived_values = []
    estdays_fvv = tracker_views.FieldValueView(
        self.estdays_fd, self.config, values, derived_values, ['defect'],
        phase_name='Gate')
    self.assertEqual('EstDays', estdays_fvv.field_def.field_name)
    self.assertEqual(3, estdays_fvv.field_def.min_value)
    self.assertEqual(99, estdays_fvv.field_def.max_value)
    self.assertEqual([], estdays_fvv.values)
    self.assertEqual([], estdays_fvv.derived_values)

  def testSomeValues(self):
    """We can create a FieldValueView with some values."""
    values = [template_helpers.EZTItem(val=12, docstring=None, idx=0)]
    derived_values = [template_helpers.EZTItem(val=88, docstring=None, idx=0)]
    estdays_fvv = tracker_views.FieldValueView(
        self.estdays_fd, self.config, values, derived_values, ['defect'])
    self.assertEqual(values, estdays_fvv.values)
    self.assertEqual(derived_values, estdays_fvv.derived_values)
    self.assertEqual('', estdays_fvv.phase_name)
    self.assertEqual(ezt.boolean(False), estdays_fvv.field_def.is_phase_field)

  def testApplicability(self):
    """We know whether a field should show an editing widget."""
    # Not the right type and has no values.
    designdoc_fvv = tracker_views.FieldValueView(
        self.designdoc_fd, self.config, [], [], ['defect'])
    self.assertFalse(designdoc_fvv.applicable)
    self.assertEqual('', designdoc_fvv.phase_name)
    self.assertEqual(ezt.boolean(False), designdoc_fvv.field_def.is_phase_field)

    # Has a value.
    designdoc_fvv = tracker_views.FieldValueView(
        self.designdoc_fd, self.config, ['fake value item'], [], ['defect'])
    self.assertTrue(designdoc_fvv.applicable)

    # Derived values don't cause editing fields to display.
    designdoc_fvv = tracker_views.FieldValueView(
        self.designdoc_fd, self.config, [], ['fake value item'], ['defect'])
    self.assertFalse(designdoc_fvv.applicable)

    # Applicable to this type of issue.
    designdoc_fvv = tracker_views.FieldValueView(
        self.designdoc_fd, self.config, [], [], ['enhancement'])
    self.assertTrue(designdoc_fvv.applicable)

    # Applicable to some issues in a bulk edit.
    designdoc_fvv = tracker_views.FieldValueView(
        self.designdoc_fd, self.config, [], [],
        ['defect', 'task', 'enhancement'])
    self.assertTrue(designdoc_fvv.applicable)

    # Applicable to all issues.
    estdays_fvv = tracker_views.FieldValueView(
        self.estdays_fd, self.config, [], [], ['enhancement'])
    self.assertTrue(estdays_fvv.applicable)

    # Explicitly set to be applicable when showing bounce values.
    designdoc_fvv = tracker_views.FieldValueView(
        self.designdoc_fd, self.config, [], [], ['defect'],
        applicable=True)
    self.assertTrue(designdoc_fvv.applicable)

  def testDisplay(self):
    """We know when a value (or --) should be shown in the metadata column."""
    # Not the right type and has no values.
    designdoc_fvv = tracker_views.FieldValueView(
        self.designdoc_fd, self.config, [], [], ['defect'])
    self.assertFalse(designdoc_fvv.display)

    # Has a value.
    designdoc_fvv = tracker_views.FieldValueView(
        self.designdoc_fd, self.config, ['fake value item'], [], ['defect'])
    self.assertTrue(designdoc_fvv.display)

    # Has a derived value.
    designdoc_fvv = tracker_views.FieldValueView(
        self.designdoc_fd, self.config, [], ['fake value item'], ['defect'])
    self.assertTrue(designdoc_fvv.display)

    # Applicable to this type of issue, it will show "--".
    designdoc_fvv = tracker_views.FieldValueView(
        self.designdoc_fd, self.config, [], [], ['enhancement'])
    self.assertTrue(designdoc_fvv.display)

    # Applicable to all issues, it will show "--".
    estdays_fvv = tracker_views.FieldValueView(
        self.estdays_fd, self.config, [], [], ['enhancement'])
    self.assertTrue(estdays_fvv.display)

  def testPhaseField(self):
    mtarget_fvv = tracker_views.FieldValueView(
        self.mtarget_fd, self.config, [], [], [], phase_name='Stage')
    self.assertEqual('Stage', mtarget_fvv.phase_name)
    self.assertEqual(ezt.boolean(True), mtarget_fvv.field_def.is_phase_field)


class FVVFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_pb2.ProjectIssueConfig()
    self.estdays_fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'EstDays', tracker_pb2.FieldTypes.INT_TYPE, None,
        None, False, False, False, 3, 99, None, False, None, None,
        None, 'no_action', 'descriptive docstring', False, None, False)
    self.os_fd = tracker_bizobj.MakeFieldDef(
        2, 789, 'OS', tracker_pb2.FieldTypes.ENUM_TYPE,
        'Enhancement', None, False, False, False, None, None, None,
        False, None, None, None, 'no_action', 'descriptive docstring',
        False, None, False)
    self.milestone_fd = tracker_bizobj.MakeFieldDef(
        3, 789, 'Launch-Milestone', tracker_pb2.FieldTypes.ENUM_TYPE,
        'Enhancement', None, False, False, False, None, None, None,
        False, None, None, None, 'no_action', 'descriptive docstring',
        False, None, False)
    self.config.field_defs = [self.estdays_fd, self.os_fd, self.milestone_fd]
    self.config.well_known_labels = [
        tracker_pb2.LabelDef(
            label='Priority-High', label_docstring='Must be resolved'),
        tracker_pb2.LabelDef(
            label='Priority-Low', label_docstring='Can be slipped'),
        ]

  def testPrecomputeInfoForValueViews_NoValues(self):
    """We can precompute info needed for an issue with no fields or labels."""
    labels = []
    derived_labels = []
    field_values = []
    phases = []
    precomp_view_info = tracker_views._PrecomputeInfoForValueViews(
        labels, derived_labels, field_values, self.config, phases)
    (labels_by_prefix, der_labels_by_prefix, field_values_by_id,
     label_docs, phases_by_name) = precomp_view_info
    self.assertEqual({}, labels_by_prefix)
    self.assertEqual({}, der_labels_by_prefix)
    self.assertEqual({}, field_values_by_id)
    self.assertEqual(
        {'priority-high': 'Must be resolved',
         'priority-low': 'Can be slipped'},
        label_docs)
    self.assertEqual({}, phases_by_name)

  def testPrecomputeInfoForValueViews_SomeValues(self):
    """We can precompute info needed for an issue with fields and labels."""
    labels = ['Priority-Low', 'GoodFirstBug', 'Feature-UI', 'Feature-Installer',
              'Launch-Milestone-66']
    derived_labels = ['OS-Windows', 'OS-Linux']
    field_values = [
        tracker_bizobj.MakeFieldValue(1, 5, None, None, None, None, False),
        ]
    phase_1 = tracker_pb2.Phase(phase_id=1, name='Stable')
    phase_2 = tracker_pb2.Phase(phase_id=2, name='Beta')
    phase_3 = tracker_pb2.Phase(phase_id=3, name='stable')
    precomp_view_info = tracker_views._PrecomputeInfoForValueViews(
        labels, derived_labels, field_values, self.config,
        phases=[phase_1, phase_2, phase_3])
    (labels_by_prefix, der_labels_by_prefix, field_values_by_id,
     _label_docs, phases_by_name) = precomp_view_info
    self.assertEqual(
        {'priority': ['Low'],
         'feature': ['UI', 'Installer'],
         'launch-milestone': ['66']},
        labels_by_prefix)
    self.assertEqual(
        {'os': ['Windows', 'Linux']},
        der_labels_by_prefix)
    self.assertEqual(
        {1: field_values},
        field_values_by_id)
    self.assertEqual(
        {'stable': [phase_1, phase_3],
         'beta': [phase_2]},
        phases_by_name)

  def testMakeAllFieldValueViews(self):
    labels = ['Priority-Low', 'GoodFirstBug', 'Feature-UI', 'Feature-Installer',
              'Launch-Milestone-66']
    derived_labels = ['OS-Windows', 'OS-Linux']
    self.config.field_defs.append(tracker_bizobj.MakeFieldDef(
        4, 789, 'UIMocks', tracker_pb2.FieldTypes.URL_TYPE,
        'Enhancement', None, False, False, False, None, None, None,
        False, None, None, None, 'no_action', 'descriptive docstring',
        False, approval_id=23, is_phase_field=False))
    self.config.field_defs.append(tracker_bizobj.MakeFieldDef(
        5, 789, 'LegalFAQs', tracker_pb2.FieldTypes.URL_TYPE,
        'Enhancement', None, False, False, False, None, None, None,
        False, None, None, None, 'no_action', 'descriptive docstring',
        False, approval_id=26, is_phase_field=False))
    self.config.field_defs.append(tracker_bizobj.MakeFieldDef(
        23, 789, 'Legal', tracker_pb2.FieldTypes.APPROVAL_TYPE,
        'Enhancement', None, False, False, False, None, None, None,
        False, None, None, None, 'no_action', 'descriptive docstring',
        False, approval_id=None, is_phase_field=False))
    self.config.field_defs.append(tracker_bizobj.MakeFieldDef(
        26, 789, 'UI', tracker_pb2.FieldTypes.APPROVAL_TYPE,
        'Enhancement', None, False, False, False, None, None, None,
        False, None, None, None, 'no_action', 'descriptive docstring',
        False, approval_id=None, is_phase_field=False))
    self.config.field_defs.append(tracker_bizobj.MakeFieldDef(
        27, 789, 'M-Target', tracker_pb2.FieldTypes.INT_TYPE,
        'Enhancement', None, False, False, False, None, None, None,
        False, None, None, None, 'no_action', 'descriptive docstring',
        False, approval_id=None, is_phase_field=True))
    field_values = [
        tracker_bizobj.MakeFieldValue(1, 5, None, None, None, None, False),
        tracker_bizobj.MakeFieldValue(
            27, 74, None, None, None, None, False, phase_id=3),
        # phase_id=4 does not belong to any of the phases given below.
        # this field value should not show up in the views.
        tracker_bizobj.MakeFieldValue(
            27, 79, None, None, None, None, False, phase_id=4),
        ]
    users_by_id = {}
    phase_1 = tracker_pb2.Phase(phase_id=1, name='Stable')
    phase_2 = tracker_pb2.Phase(phase_id=2, name='Beta')
    phase_3 = tracker_pb2.Phase(phase_id=3, name='stable')
    fvvs = tracker_views.MakeAllFieldValueViews(
        self.config, labels, derived_labels, field_values, users_by_id,
        parent_approval_ids=[23], phases=[phase_1, phase_2, phase_3])
    self.assertEqual(9, len(fvvs))
    # Values are sorted by (applicable_type, field_name).
    logging.info([fv.field_name for fv in fvvs])
    (estdays_fvv, launch_milestone_fvv, legal_fvv, legal_faq_fvv,
      beta_mtarget_fvv, stable_mtarget_fvv, os_fvv, ui_fvv, ui_mocks_fvv) = fvvs
    self.assertEqual('EstDays', estdays_fvv.field_name)
    self.assertEqual(1, len(estdays_fvv.values))
    self.assertEqual(0, len(estdays_fvv.derived_values))
    self.assertEqual('Launch-Milestone', launch_milestone_fvv.field_name)
    self.assertEqual(1, len(launch_milestone_fvv.values))
    self.assertEqual(0, len(launch_milestone_fvv.derived_values))
    self.assertEqual('OS', os_fvv.field_name)
    self.assertEqual(0, len(os_fvv.values))
    self.assertEqual(2, len(os_fvv.derived_values))
    self.assertEqual(ui_mocks_fvv.field_name, 'UIMocks')
    self.assertEqual(ui_mocks_fvv.phase_name, '')
    self.assertTrue(ui_mocks_fvv.applicable)
    self.assertEqual(legal_faq_fvv.field_name, 'LegalFAQs')
    self.assertFalse(legal_faq_fvv.applicable)
    self.assertFalse(legal_fvv.applicable)
    self.assertFalse(ui_fvv.applicable)
    self.assertEqual('M-Target', stable_mtarget_fvv.field_name)
    self.assertEqual('stable', stable_mtarget_fvv.phase_name)
    self.assertEqual(1, len(stable_mtarget_fvv.values))
    self.assertEqual(74, stable_mtarget_fvv.values[0].val)
    self.assertEqual(0, len(stable_mtarget_fvv.derived_values))
    self.assertEqual('M-Target', beta_mtarget_fvv.field_name)
    self.assertEqual('beta', beta_mtarget_fvv.phase_name)
    self.assertEqual(0, len(beta_mtarget_fvv.values))
    self.assertEqual(0, len(beta_mtarget_fvv.values))

  def testMakeFieldValueView(self):
    pass  # Covered by testMakeAllFieldValueViews()

  def testMakeFieldValueItemsTest(self):
    pass  # Covered by testMakeAllFieldValueViews()

  def testMakeBounceFieldValueViews(self):
    config = tracker_pb2.ProjectIssueConfig()
    fd = tracker_pb2.FieldDef(
        field_id=3, field_type=tracker_pb2.FieldTypes.INT_TYPE,
        applicable_type='', field_name='EstDays')
    phase_fd = tracker_pb2.FieldDef(
        field_id=4, field_type=tracker_pb2.FieldTypes.INT_TYPE,
        applicable_type='', field_name='Gump')
    config.field_defs = [fd,
                         phase_fd,
                         tracker_pb2.FieldDef(
        field_id=5, field_type=tracker_pb2.FieldTypes.STR_TYPE)
    ]
    parsed_fvs = {3: [455]}
    parsed_phase_fvs = {
        4: {'stable': [73, 74], 'beta': [8], 'beta-exp': [75]},
    }
    fvs = tracker_views.MakeBounceFieldValueViews(
        parsed_fvs, parsed_phase_fvs, config)

    self.assertEqual(len(fvs), 4)

    estdays_ezt_fv = template_helpers.EZTItem(val=455, docstring='', idx=0)
    expected = tracker_views.FieldValueView(
        fd, config, [estdays_ezt_fv], [], [])
    self.assertEqual(fvs[0].field_name, expected.field_name)
    self.assertEqual(fvs[0].values[0].val, expected.values[0].val)
    self.assertEqual(fvs[0].values[0].idx, expected.values[0].idx)
    self.assertTrue(fvs[0].applicable)

    self.assertEqual(fvs[1].field_name, phase_fd.field_name)
    self.assertEqual(fvs[2].field_name, phase_fd.field_name)
    self.assertEqual(fvs[3].field_name, phase_fd.field_name)

    fd.approval_id = 23
    config.field_defs = [fd,
                         tracker_pb2.FieldDef(
                             field_id=23, field_name='Legal',
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)]
    fvs = tracker_views.MakeBounceFieldValueViews(parsed_fvs, {}, config)
    self.assertTrue(fvs[0].applicable)


class ConvertLabelsToFieldValuesTest(unittest.TestCase):

  def testConvertLabelsToFieldValues_NoLabels(self):
    result = tracker_views._ConvertLabelsToFieldValues(
        [], 'opsys', {})
    self.assertEqual([], result)

  def testConvertLabelsToFieldValues_NoMatch(self):
    result = tracker_views._ConvertLabelsToFieldValues(
        [], 'opsys', {})
    self.assertEqual([], result)

  def testConvertLabelsToFieldValues_HasMatch(self):
    result = tracker_views._ConvertLabelsToFieldValues(
        ['OSX'], 'opsys', {})
    self.assertEqual(1, len(result))
    self.assertEqual('OSX', result[0].val)
    self.assertEqual('', result[0].docstring)

    result = tracker_views._ConvertLabelsToFieldValues(
        ['OSX', 'All'], 'opsys', {'opsys-all': 'Happens everywhere'})
    self.assertEqual(2, len(result))
    self.assertEqual('OSX', result[0].val)
    self.assertEqual('', result[0].docstring)
    self.assertEqual('All', result[1].val)
    self.assertEqual('Happens everywhere', result[1].docstring)


class FieldDefViewTest(unittest.TestCase):

  def setUp(self):
    self.approval_fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'LaunchApproval', tracker_pb2.FieldTypes.APPROVAL_TYPE, None,
        None, True, True, False, 3, 99, None, False, None, None,
        None, 'no_action', 'descriptive docstring', False, None, False)

    self.approval_def = tracker_pb2.ApprovalDef(
        approval_id=1, approver_ids=[111], survey='question?')

    self.field_def = tracker_bizobj.MakeFieldDef(
        2, 789, 'AffectedUsers', tracker_pb2.FieldTypes.INT_TYPE, None,
        None, True, True, False, 3, 99, None, False, None, None,
        None, 'no_action', 'descriptive docstring', False, 1, False)

  def testFieldDefView_Normal(self):
    config = _MakeConfig()
    config.field_defs.append(self.approval_fd)
    config.approval_defs.append(self.approval_def)
    view = tracker_views.FieldDefView(self.field_def, config)
    self.assertEqual('AffectedUsers', view.field_name)
    self.assertEqual('descriptive docstring', view.docstring_short)
    self.assertEqual('INT_TYPE', view.type_name)
    self.assertEqual([], view.choices)
    self.assertEqual('required', view.importance)
    self.assertEqual(3, view.min_value)
    self.assertEqual(99, view.max_value)
    self.assertEqual('no_action', view.date_action_str)
    self.assertEqual(view.approval_id, 1)
    self.assertEqual(view.is_approval_subfield, ezt.boolean(True))
    self.assertEqual(view.approvers, [])
    self.assertEqual(view.survey, '')
    self.assertEqual(view.survey_questions, [])
    self.assertIsNone(view.is_phase_field)

  def testFieldDefView_Approval(self):
    config = _MakeConfig()
    approver_view = framework_views.StuffUserView(
        111, 'shouldnotmatter@ch.org', False)
    user_views = {111: approver_view}

    view = tracker_views.FieldDefView(
        self.approval_fd, config,
        user_views= user_views, approval_def=self.approval_def)
    self.assertEqual(view.approvers, [approver_view])
    self.assertEqual(view.survey, self.approval_def.survey)
    self.assertEqual(view.survey_questions, [view.survey])

    self.approval_def.survey = None
    view = tracker_views.FieldDefView(
        self.approval_fd, config,
        user_views= user_views, approval_def=self.approval_def)
    self.assertEqual(view.survey, '')
    self.assertEqual(view.survey_questions, [])

    self.approval_def.survey = 'Q1\nQ2\nQ3'
    view = tracker_views.FieldDefView(
        self.approval_fd, config,
        user_views= user_views, approval_def=self.approval_def)
    self.assertEqual(view.survey, self.approval_def.survey)
    self.assertEqual(view.survey_questions, ['Q1', 'Q2', 'Q3'])


class IssueTemplateViewTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class MakeFieldUserViewsTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class ConfigViewTest(unittest.TestCase):
  pass  # TODO(jrobbins): write tests


class ConfigFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(768)

  def testStatusDefsAsText(self):
    open_text, closed_text = tracker_views.StatusDefsAsText(self.config)

    for wks in tracker_constants.DEFAULT_WELL_KNOWN_STATUSES:
      status, doc, means_open, _deprecated = wks
      if means_open:
        self.assertIn(status, open_text)
        self.assertIn(doc, open_text)
      else:
        self.assertIn(status, closed_text)
        self.assertIn(doc, closed_text)

    self.assertEqual(
        len(tracker_constants.DEFAULT_WELL_KNOWN_STATUSES),
        len(open_text.split('\n')) + len(closed_text.split('\n')))

  def testLabelDefsAsText(self):
    # Note: Day-Monday will not be part of the result because it is masked.
    self.config.field_defs.append(tracker_pb2.FieldDef(
        field_id=1, field_name='Day',
        field_type=tracker_pb2.FieldTypes.ENUM_TYPE))
    self.config.well_known_labels.append(tracker_pb2.LabelDef(
        label='Day-Monday'))
    labels_text = tracker_views.LabelDefsAsText(self.config)

    for wkl in tracker_constants.DEFAULT_WELL_KNOWN_LABELS:
      label, doc, _deprecated = wkl
      self.assertIn(label, labels_text)
      self.assertIn(doc, labels_text)
    self.assertEqual(
        len(tracker_constants.DEFAULT_WELL_KNOWN_LABELS),
        len(labels_text.split('\n')))
