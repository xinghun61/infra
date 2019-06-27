# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the issue admin pages."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mox
import unittest

from mock import Mock, patch

from framework import permissions
from framework import urls
from proto import tracker_pb2
from services import service_manager
from services import template_svc
from testing import fake
from testing import testing_helpers
from tracker import issueadmin
from tracker import tracker_bizobj
from tracker import tracker_constants


class TestBase(unittest.TestCase):

  def setUpServlet(self, servlet_factory):
    # pylint: disable=attribute-defined-outside-init
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        user=fake.UserService(),
        issue=fake.IssueService(),
        template=Mock(spec=template_svc.TemplateService),
        features=fake.FeaturesService())
    self.servlet = servlet_factory('req', 'res', services=self.services)
    self.project = self.services.project.TestAddProject(
        'proj', project_id=789, contrib_ids=[333])
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.services.config.StoreConfig(None, self.config)
    self.cnxn = fake.MonorailConnection()
    self.mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/admin', project=self.project)
    self.mox = mox.Mox()
    self.test_template = tracker_bizobj.MakeIssueTemplate(
        'Test Template', 'sum', 'New', 111, 'content', [], [], [], [])
    self.test_template.template_id = 12345
    self.test_templates = testing_helpers.DefaultTemplates()
    self.test_templates.append(self.test_template)
    self.services.template.GetProjectTemplates\
        .return_value = self.test_templates
    self.services.template.GetTemplateSetForProject\
        .return_value = [(12345, 'Test template', 0)]

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def _mockGetUser(self):
    self.mox.StubOutWithMock(self.services.user, 'GetUser')
    user = self.services.user.TestAddUser('user@invalid', 100)
    self.services.user.GetUser(
        mox.IgnoreArg(), mox.IgnoreArg()).MultipleTimes().AndReturn(user)


class IssueAdminBaseTest(TestBase):

  def setUp(self):
    super(IssueAdminBaseTest, self).setUpServlet(issueadmin.IssueAdminBase)

  def testGatherPageData(self):
    self._mockGetUser()
    self.mox.ReplayAll()
    page_data = self.servlet.GatherPageData(self.mr)
    self.mox.VerifyAll()

    self.assertItemsEqual(
        ['admin_tab_mode', 'config', 'open_text', 'closed_text', 'labels_text'],
        list(page_data.keys()))
    config_view = page_data['config']
    self.assertEqual(789, config_view.project_id)


class AdminStatusesTest(TestBase):

  def setUp(self):
    super(AdminStatusesTest, self).setUpServlet(issueadmin.AdminStatuses)

  @patch('framework.servlet.Servlet.PleaseCorrect')
  def testProcessSubtabForm_MissingInput(self, mock_pc):
    post_data = fake.PostData()
    next_url = self.servlet.ProcessSubtabForm(post_data, self.mr)
    self.assertIsNone(next_url)
    mock_pc.assert_called_once()
    self.assertEqual(len(tracker_constants.DEFAULT_WELL_KNOWN_STATUSES),
                     len(self.config.well_known_statuses))
    self.assertEqual(tracker_constants.DEFAULT_STATUSES_OFFER_MERGE,
                     self.config.statuses_offer_merge)

  @patch('framework.servlet.Servlet.PleaseCorrect')
  def testProcessSubtabForm_EmptyInput(self, mock_pc):
    post_data = fake.PostData(
        predefinedopen=[''], predefinedclosed=[''], statuses_offer_merge=[''])
    next_url = self.servlet.ProcessSubtabForm(post_data, self.mr)
    self.assertIsNone(next_url)
    mock_pc.assert_called_once()
    self.assertEqual(len(tracker_constants.DEFAULT_WELL_KNOWN_STATUSES),
                     len(self.config.well_known_statuses))
    self.assertEqual(tracker_constants.DEFAULT_STATUSES_OFFER_MERGE,
                     self.config.statuses_offer_merge)

  def testProcessSubtabForm_Normal(self):
    post_data = fake.PostData(
        predefinedopen=['New = newly reported'],
        predefinedclosed=['Fixed\nDuplicate'],
        statuses_offer_merge=['Duplicate'])
    next_url = self.servlet.ProcessSubtabForm(post_data, self.mr)
    self.assertEqual(urls.ADMIN_STATUSES, next_url)
    self.assertEqual(3, len(self.config.well_known_statuses))
    self.assertEqual('New', self.config.well_known_statuses[0].status)
    self.assertTrue(self.config.well_known_statuses[0].means_open)
    self.assertEqual('Fixed', self.config.well_known_statuses[1].status)
    self.assertFalse(self.config.well_known_statuses[1].means_open)
    self.assertEqual('Duplicate', self.config.well_known_statuses[2].status)
    self.assertFalse(self.config.well_known_statuses[2].means_open)
    self.assertEqual(['Duplicate'], self.config.statuses_offer_merge)


class AdminLabelsTest(TestBase):

  def setUp(self):
    super(AdminLabelsTest, self).setUpServlet(issueadmin.AdminLabels)

  def testGatherPageData(self):
    self._mockGetUser()
    self.mox.ReplayAll()
    page_data = self.servlet.GatherPageData(self.mr)
    self.mox.VerifyAll()

    self.assertItemsEqual(
        ['admin_tab_mode', 'config', 'field_defs',
         'open_text', 'closed_text', 'labels_text'],
        list(page_data.keys()))
    config_view = page_data['config']
    self.assertEqual(789, config_view.project_id)
    self.assertEqual([], page_data['field_defs'])

  @patch('framework.servlet.Servlet.PleaseCorrect')
  def testProcessSubtabForm_MissingInput(self, mock_pc):
    post_data = fake.PostData()
    next_url = self.servlet.ProcessSubtabForm(post_data, self.mr)
    self.assertIsNone(next_url)
    mock_pc.assert_called_once()
    self.assertEqual(len(tracker_constants.DEFAULT_WELL_KNOWN_LABELS),
                     len(self.config.well_known_labels))
    self.assertEqual(tracker_constants.DEFAULT_EXCL_LABEL_PREFIXES,
                     self.config.exclusive_label_prefixes)

  @patch('framework.servlet.Servlet.PleaseCorrect')
  def testProcessSubtabForm_EmptyInput(self, mock_pc):
    post_data = fake.PostData(
        predefinedlabels=[''], excl_prefixes=[''])
    next_url = self.servlet.ProcessSubtabForm(post_data, self.mr)
    self.assertIsNone(next_url)  # Because PleaseCorrect() was called.
    mock_pc.assert_called_once()
    self.assertEqual(len(tracker_constants.DEFAULT_WELL_KNOWN_LABELS),
                     len(self.config.well_known_labels))
    self.assertEqual(tracker_constants.DEFAULT_EXCL_LABEL_PREFIXES,
                     self.config.exclusive_label_prefixes)

  def testProcessSubtabForm_Normal(self):
    post_data = fake.PostData(
        predefinedlabels=['Pri-0 = Burning issue\nPri-4 = It can wait'],
        excl_prefixes=['pri'])
    next_url = self.servlet.ProcessSubtabForm(post_data, self.mr)
    self.assertEqual(urls.ADMIN_LABELS, next_url)
    self.assertEqual(2, len(self.config.well_known_labels))
    self.assertEqual('Pri-0', self.config.well_known_labels[0].label)
    self.assertEqual('Pri-4', self.config.well_known_labels[1].label)
    self.assertEqual(['pri'], self.config.exclusive_label_prefixes)

  @patch('framework.servlet.Servlet.PleaseCorrect')
  def testProcessSubtabForm_Duplicates(self, mock_pc):
    post_data = fake.PostData(
        predefinedlabels=['Pri-0\nPri-4\npri-0'],
        excl_prefixes=['pri'])
    next_url = self.servlet.ProcessSubtabForm(post_data, self.mr)
    self.assertIsNone(next_url)
    mock_pc.assert_called_once()
    self.assertEqual(
        'Duplicate label: pri-0',
        self.mr.errors.label_defs)

  @patch('framework.servlet.Servlet.PleaseCorrect')
  def testProcessSubtabForm_Conflict(self, mock_pc):
    post_data = fake.PostData(
        predefinedlabels=['Multi-Part-One\nPri-4\npri-0'],
        excl_prefixes=['pri'])
    self.config.field_defs = [
        tracker_pb2.FieldDef(
            field_name='Multi-Part',
            field_type=tracker_pb2.FieldTypes.ENUM_TYPE)]
    next_url = self.servlet.ProcessSubtabForm(post_data, self.mr)
    self.assertIsNone(next_url)
    mock_pc.assert_called_once()
    self.assertEqual(
        'Label "Multi-Part-One" should be defined in enum "multi-part"',
        self.mr.errors.label_defs)


class AdminTemplatesTest(TestBase):

  def setUp(self):
    super(AdminTemplatesTest, self).setUpServlet(issueadmin.AdminTemplates)
    self.mr.auth.user_id = 333
    self.mr.auth.effective_ids = {333}

  def testGatherPageData(self):
    self._mockGetUser()
    self.mox.ReplayAll()
    page_data = self.servlet.GatherPageData(self.mr)
    self.mox.VerifyAll()

    config_view = page_data['config']
    self.assertEqual(789, config_view.project_id)

  def testProcessSubtabForm_NoEditProjectPerm(self):
    """If user lacks perms, raise an exception."""
    post_data = fake.PostData(
        default_template_for_developers=['Test Template'],
        default_template_for_users=['Test Template'])
    self.mr.perms = permissions.EMPTY_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.ProcessSubtabForm, post_data, self.mr)
    self.assertEqual(0, self.config.default_template_for_developers)
    self.assertEqual(0, self.config.default_template_for_users)

  def testProcessSubtabForm_Normal(self):
    """If user has perms, set default templates."""
    post_data = fake.PostData(
        default_template_for_developers=['Test Template'],
        default_template_for_users=['Test Template'])
    next_url = self.servlet.ProcessSubtabForm(post_data, self.mr)
    self.assertEqual(urls.ADMIN_TEMPLATES, next_url)
    self.assertEqual(12345, self.config.default_template_for_developers)
    self.assertEqual(12345, self.config.default_template_for_users)

  def testParseDefaultTemplateSelections_NotSpecified(self):
    post_data = fake.PostData()
    for_devs, for_users = self.servlet._ParseDefaultTemplateSelections(
        post_data, self.test_templates)
    self.assertEqual(None, for_devs)
    self.assertEqual(None, for_users)

  def testParseDefaultTemplateSelections_TemplateNotFoundIsIgnored(self):
    post_data = fake.PostData(
        default_template_for_developers=['Bad value'],
        default_template_for_users=['Bad value'])
    for_devs, for_users = self.servlet._ParseDefaultTemplateSelections(
        post_data, self.test_templates)
    self.assertEqual(None, for_devs)
    self.assertEqual(None, for_users)

  def testParseDefaultTemplateSelections_Normal(self):
    post_data = fake.PostData(
        default_template_for_developers=['Test Template'],
        default_template_for_users=['Test Template'])
    for_devs, for_users = self.servlet._ParseDefaultTemplateSelections(
        post_data, self.test_templates)
    self.assertEqual(12345, for_devs)
    self.assertEqual(12345, for_users)


class AdminComponentsTest(TestBase):

  def setUp(self):
    super(AdminComponentsTest, self).setUpServlet(issueadmin.AdminComponents)
    self.cd_clean = tracker_bizobj.MakeComponentDef(
        1, self.project.project_id, 'BackEnd', 'doc', False, [], [111], 100000,
        122, 10000000, 133)
    self.cd_with_subcomp = tracker_bizobj.MakeComponentDef(
        2, self.project.project_id, 'FrontEnd', 'doc', False, [], [111],
        100000, 122, 10000000, 133)
    self.subcd = tracker_bizobj.MakeComponentDef(
        3, self.project.project_id, 'FrontEnd>Worker', 'doc', False, [], [111],
        100000, 122, 10000000, 133)
    self.cd_with_template = tracker_bizobj.MakeComponentDef(
        4, self.project.project_id, 'Middle', 'doc', False, [], [111],
        100000, 122, 10000000, 133)

  def testGatherPageData(self):
    self._mockGetUser()
    self.mox.ReplayAll()
    page_data = self.servlet.GatherPageData(self.mr)
    self.mox.VerifyAll()
    self.assertItemsEqual(
        ['admin_tab_mode', 'failed_templ', 'component_defs', 'failed_perm',
         'config', 'failed_subcomp',
         'open_text', 'closed_text', 'labels_text'],
        list(page_data.keys()))
    config_view = page_data['config']
    self.assertEqual(789, config_view.project_id)
    self.assertEqual([], page_data['component_defs'])

  def testProcessFormData_NoErrors(self):
    self.config.component_defs = [
        self.cd_clean, self.cd_with_subcomp, self.subcd, self.cd_with_template]
    self.services.template.TemplatesWithComponent.return_value = []
    post_data = {
        'delete_components' : '%s,%s,%s' % (
            self.cd_clean.path, self.cd_with_subcomp.path, self.subcd.path)}
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue(
        url.startswith('http://127.0.0.1/p/proj/adminComponents?deleted='
                       'FrontEnd%3EWorker%2CFrontEnd%2CBackEnd&failed_perm=&'
                       'failed_subcomp=&failed_templ=&ts='))

  def testProcessFormData_SubCompError(self):
    self.config.component_defs = [
        self.cd_clean, self.cd_with_subcomp, self.subcd, self.cd_with_template]
    self.services.template.TemplatesWithComponent.return_value = []
    post_data = {
        'delete_components' : '%s,%s' % (
            self.cd_clean.path, self.cd_with_subcomp.path)}
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue(
        url.startswith('http://127.0.0.1/p/proj/adminComponents?deleted='
                       'BackEnd&failed_perm=&failed_subcomp=FrontEnd&'
                       'failed_templ=&ts='))

  def testProcessFormData_TemplateError(self):
    self.config.component_defs = [
        self.cd_clean, self.cd_with_subcomp, self.subcd, self.cd_with_template]

    def mockTemplatesWithComponent(_cnxn, component_id):
      if component_id == 4:
        return 'template'
    self.services.template.TemplatesWithComponent\
        .side_effect = mockTemplatesWithComponent

    post_data = {
        'delete_components' : '%s,%s,%s,%s' % (
            self.cd_clean.path, self.cd_with_subcomp.path, self.subcd.path,
            self.cd_with_template.path)}
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue(
        url.startswith('http://127.0.0.1/p/proj/adminComponents?deleted='
                       'FrontEnd%3EWorker%2CFrontEnd%2CBackEnd&failed_perm=&'
                       'failed_subcomp=&failed_templ=Middle&ts='))


class AdminViewsTest(TestBase):

  def setUp(self):
    super(AdminViewsTest, self).setUpServlet(issueadmin.AdminViews)

  def testGatherPageData(self):
    self._mockGetUser()
    self.mox.ReplayAll()
    page_data = self.servlet.GatherPageData(self.mr)
    self.mox.VerifyAll()

    self.assertItemsEqual(
        ['canned_queries', 'admin_tab_mode', 'config', 'issue_notify',
         'new_query_indexes', 'max_queries',
         'open_text', 'closed_text', 'labels_text'],
        list(page_data.keys()))
    config_view = page_data['config']
    self.assertEqual(789, config_view.project_id)

  def testProcessSubtabForm(self):
    post_data = fake.PostData(
        default_col_spec=['id pri mstone owner status summary'],
        default_sort_spec=['mstone pri'],
        default_x_attr=['owner'], default_y_attr=['mstone'])
    next_url = self.servlet.ProcessSubtabForm(post_data, self.mr)
    self.assertEqual(urls.ADMIN_VIEWS, next_url)
    self.assertEqual(
        'id pri mstone owner status summary', self.config.default_col_spec)
    self.assertEqual('mstone pri', self.config.default_sort_spec)
    self.assertEqual('owner', self.config.default_x_attr)
    self.assertEqual('mstone', self.config.default_y_attr)


class AdminViewsFunctionsTest(unittest.TestCase):

  def testParseListPreferences(self):
    # If no input, col_spec will be default column spec.
    # For other fiels empty strings should be returned.
    (col_spec, sort_spec, x_attr, y_attr, member_default_query,
     ) = issueadmin._ParseListPreferences({})
    self.assertEqual(tracker_constants.DEFAULT_COL_SPEC, col_spec)
    self.assertEqual('', sort_spec)
    self.assertEqual('', x_attr)
    self.assertEqual('', y_attr)
    self.assertEqual('', member_default_query)

    # Test how hyphens in input are treated.
    spec = 'label1-sub1  label2  label3-sub3'
    (col_spec, sort_spec, x_attr, y_attr, member_default_query,
     ) = issueadmin._ParseListPreferences(
        fake.PostData(default_col_spec=[spec],
                      default_sort_spec=[spec],
                      default_x_attr=[spec],
                      default_y_attr=[spec]),
        )

    # Hyphens (and anything following) should be stripped from each term.
    self.assertEqual('label1-sub1 label2 label3-sub3', col_spec)

    # The sort spec should be as given (except with whitespace condensed).
    self.assertEqual(' '.join(spec.split()), sort_spec)

    # Only the first term (up to the first hyphen) should be used for x- or
    # y-attr.
    self.assertEqual('label1-sub1', x_attr)
    self.assertEqual('label1-sub1', y_attr)

    # Test that multibyte strings are not mangled.
    spec = ('\xe7\xaa\xbf\xe8\x8b\xa5-\xe7\xb9\xb9 '
            '\xe5\x9c\xb0\xe3\x81\xa6-\xe5\xbd\x93-\xe3\x81\xbe\xe3\x81\x99')
    spec = spec.decode('utf-8')
    (col_spec, sort_spec, x_attr, y_attr, member_default_query,
     ) = issueadmin._ParseListPreferences(
        fake.PostData(default_col_spec=[spec],
                      default_sort_spec=[spec],
                      default_x_attr=[spec],
                      default_y_attr=[spec],
                      member_default_query=[spec]),
        )
    self.assertEqual(spec, col_spec)
    self.assertEqual(' '.join(spec.split()), sort_spec)
    self.assertEqual('\xe7\xaa\xbf\xe8\x8b\xa5-\xe7\xb9\xb9'.decode('utf-8'),
                     x_attr)
    self.assertEqual('\xe7\xaa\xbf\xe8\x8b\xa5-\xe7\xb9\xb9'.decode('utf-8'),
                     y_attr)
    self.assertEqual(spec, member_default_query)


class AdminRulesTest(TestBase):

  def setUp(self):
    super(AdminRulesTest, self).setUpServlet(issueadmin.AdminRules)

  def testGatherPageData(self):
    self._mockGetUser()
    self.mox.ReplayAll()
    page_data = self.servlet.GatherPageData(self.mr)
    self.mox.VerifyAll()

    self.assertItemsEqual(
        ['admin_tab_mode', 'config', 'rules', 'new_rule_indexes',
         'max_rules', 'open_text', 'closed_text', 'labels_text'],
        list(page_data.keys()))
    config_view = page_data['config']
    self.assertEqual(789, config_view.project_id)
    self.assertEqual([], page_data['rules'])

  def testProcessSubtabForm(self):
    pass  # TODO(jrobbins): write this test
