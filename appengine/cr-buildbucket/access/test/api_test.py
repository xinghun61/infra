# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from components import auth
from components import auth_testing

from access import access_pb2
from access import api
from proto.config import project_config_pb2
from test import config_test
import config
import user

# Alias here for convenience.
Acl = project_config_pb2.Acl


class AccessApiTest(testing.AppengineTestCase):

  def setUp(self):
    super(AccessApiTest, self).setUp()
    self.servicer = api.AccessServicer()
    user.clear_request_cache()
    self.patch('components.auth.is_admin', autospec=True, return_value=False)
    self.patch(
        'components.auth.is_group_member', autospec=True, return_value=True
    )

  def test_bad_request(self):
    request = access_pb2.PermittedActionsRequest(
        resource_kind='builder',
        resource_ids=['abc', 'xyz'],
    )
    result = self.servicer.PermittedActions(request, None)
    self.assertEqual(len(result.permitted), 0)

  def test_no_permissions(self):
    request = access_pb2.PermittedActionsRequest(
        resource_kind='bucket',
        resource_ids=['luci.chromium.try', 'luci.chromium.ci'],
    )
    result = self.servicer.PermittedActions(request, None)
    self.assertEqual(len(result.permitted), 2)
    for perms in result.permitted.itervalues():
      self.assertEqual(len(perms.actions), 0)

  def test_good_request(self):
    config.put_bucket(
        'chromium',
        'a' * 40,
        config_test.parse_bucket_cfg(
            '''
            name: "try"
            acls {
              role: SCHEDULER
              identity: "anonymous:anonymous"
            }
            '''
        ),
    )
    config.put_bucket(
        'chromium',
        'a' * 40,
        config_test.parse_bucket_cfg(
            '''
            name: "ci"
            acls {
              role: READER
              identity: "anonymous:anonymous"
            }
            '''
        ),
    )

    request = access_pb2.PermittedActionsRequest(
        resource_kind='bucket',
        resource_ids=['luci.chromium.try', 'luci.chromium.ci'],
    )
    result = self.servicer.PermittedActions(request, None)
    self.assertEqual(len(result.permitted), 2)
    self.assertEqual(
        set(result.permitted.keys()),
        {'luci.chromium.try', 'luci.chromium.ci'},
    )

    try_perms = result.permitted['luci.chromium.try']
    self.assertEqual(len(try_perms.actions), 5)  # Sanity check.
    self.assertEqual(
        set(try_perms.actions),
        {action.name for action in user.ROLE_TO_ACTIONS[Acl.SCHEDULER]},
    )

    ci_perms = result.permitted['luci.chromium.ci']
    self.assertEqual(
        set(ci_perms.actions),
        {action.name for action in user.ROLE_TO_ACTIONS[Acl.READER]},
    )

  def test_description(self):
    result = self.servicer.Description(None, None)

    self.assertEqual(len(result.resources), 1)
    resource = result.resources[0]
    self.assertEqual(resource.kind, 'bucket')
    self.assertEqual(
        set(resource.actions.keys()),
        {action.name for action in user.ACTION_DESCRIPTIONS.keys()},
    )
    self.assertEqual(
        set(resource.roles.keys()),
        set(Acl.Role.keys()),
    )
