# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
from test.test_util import future
from testing_utils import testing

from access import access_pb2
from access import api
import acl
from proto import project_config_pb2

# Alias here for convenience.
Acl = project_config_pb2.Acl


class AccessApiTest(testing.AppengineTestCase):
  @mock.patch('acl.get_role_async', autospec=True)
  def test_permitted_actions(self, get_role_async):
    servicer = api.AccessServicer()

    # Test bad request.
    request = access_pb2.PermittedActionsRequest(
        resource_kind='builder',
        resource_ids=['abc', 'xyz'],
    )
    result = servicer.PermittedActions(request, None)
    self.assertEqual(len(result.permitted), 0)

    # Test no permissions.
    get_role_async.return_value = future(None)

    request = access_pb2.PermittedActionsRequest(
        resource_kind='bucket',
        resource_ids=['try', 'ci'],
    )
    result = servicer.PermittedActions(request, None)
    self.assertEqual(len(result.permitted), 2)
    for perms in result.permitted.itervalues():
      self.assertEqual(len(perms.actions), 0)

    # Test good request.
    get_role_async.return_value = future(Acl.SCHEDULER)

    result = servicer.PermittedActions(request, None)
    self.assertEqual(len(result.permitted), 2)
    self.assertEqual(
        set(result.permitted.keys()),
        {'try', 'ci'},
    )
    for perms in result.permitted.itervalues():
      self.assertEqual(
          set(perms.actions),
          {action.name for action in acl.ACTIONS_FOR_ROLE[Acl.SCHEDULER]},
      )


  def test_description(self):
    servicer = api.AccessServicer()
    result = servicer.Description(None, None)

    self.assertEqual(len(result.resources), 1)
    resource = result.resources[0]
    self.assertEqual(resource.kind, 'bucket')
    self.assertEqual(
        set(resource.actions.keys()),
        {action.name for action in acl.ACTION_DESCRIPTIONS.keys()},
    )
    self.assertEqual(
        set(resource.roles.keys()),
        set(Acl.Role.keys()),
    )
