# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.protobuf import duration_pb2

from components import auth
from components import utils

from access import access_pb2
from access import access_prpc_pb2
from proto.config import project_config_pb2
import api_common
import user

__all__ = ['AccessServicer']


def create_resource_permissions(role):
  if role is None:
    return access_pb2.PermittedActionsResponse.ResourcePermissions()
  return access_pb2.PermittedActionsResponse.ResourcePermissions(
      actions=sorted(action.name for action in user.ROLE_TO_ACTIONS[role]),
  )


class AccessServicer(object):
  """AccessServicer implements the Access API.

  AccessServicer implements the core functionality of the access service as a
  pRPC service interface.
  """

  DESCRIPTION = access_prpc_pb2.AccessServiceDescription

  def PermittedActions(self, request, _context):
    """Returns a set of permitted actions for the requested resources."""
    logging.debug(
        'Received request from %s for: %s', auth.get_current_identity(), request
    )
    if request.resource_kind != 'bucket':
      return access_pb2.PermittedActionsResponse()
    bucket_ids = dict(
        utils.async_apply(request.resource_ids, api_common.to_bucket_id_async)
    )
    roles = dict(
        utils.async_apply(bucket_ids.itervalues(), user.get_role_async)
    )
    permitted = {
        rid: create_resource_permissions(roles[bucket_ids[rid]])
        for rid in request.resource_ids
    }
    logging.debug('Permitted: %s', permitted)
    return access_pb2.PermittedActionsResponse(
        permitted=permitted,
        validity_duration=duration_pb2.Duration(seconds=10),
    )

  def Description(self, _request, _context):
    """Returns a description of actions and roles available."""
    ResourceDescription = access_pb2.DescriptionResponse.ResourceDescription
    return access_pb2.DescriptionResponse(
        resources=[
            ResourceDescription(
                kind='bucket',
                comment='A bucket of builds.',
                actions={
                    action.name: ResourceDescription.Action(comment=desc)
                    for action, desc in user.ACTION_DESCRIPTIONS.iteritems()
                },
                roles={
                    project_config_pb2.Acl.Role.Name(role):
                    access_pb2.DescriptionResponse.ResourceDescription.Role(
                        allowed_actions=sorted(
                            action.name for action in user.ROLE_TO_ACTIONS[role]
                        ),
                        comment=description,
                    )
                    for role, description in user.ROLE_DESCRIPTIONS.iteritems()
                },
            )
        ],
    )
