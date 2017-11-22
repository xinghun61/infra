# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.protobuf import empty_pb2
from google.protobuf import duration_pb2

from components import prpc

from access import access_pb2
from access import access_prpc_pb2
from proto import project_config_pb2
import acl


__all__ = ['create_routes']


def create_resource_permissions(role):
  if role is None:
    return access_pb2.PermittedActionsResponse.ResourcePermissions()
  return access_pb2.PermittedActionsResponse.ResourcePermissions(
      actions=[action.name for action in acl.ACTIONS_FOR_ROLE[role]]
  )


class AccessServicer(object):
  """AccessServicer implements the Access API.

  AccessServicer implements the core functionality of the access service as a
  pRPC service interface.
  """

  DESCRIPTION = access_prpc_pb2.AccessServiceDescription

  def PermittedActions(self, request, _context):
    """Returns a set of permitted actions for the requested resources."""
    if request.resource_kind != 'bucket':
      return access_pb2.PermittedActionsResponse()
    roles = {
      bucket: acl.get_role_async(bucket)
      for bucket in request.resource_ids
    }
    return access_pb2.PermittedActionsResponse(
        permitted={
          bucket: create_resource_permissions(role.get_result())
          for bucket, role in roles.iteritems()
        },
        validity_duration=duration_pb2.Duration(seconds=10),
    )


  def Description(self, _request, _context):
    """Returns a description of actions and roles available."""
    return access_pb2.DescriptionResponse(
        resources=[
          access_pb2.DescriptionResponse.ResourceDescription(
              kind='bucket',
              comment='A bucket of builds.',
              actions={
                action.name:
                  access_pb2.DescriptionResponse.ResourceDescription.Action(
                      comment=description,
                  )
                for action, description in acl.ACTION_DESCRIPTIONS.iteritems()
              },
              roles={
                project_config_pb2.Acl.Role.Name(role):
                  access_pb2.DescriptionResponse.ResourceDescription.Role(
                      allowed_actions=[
                        action.name for action in acl.ACTIONS_FOR_ROLE[role]
                      ],
                      comment=description,
                  )
                for role, description in acl.ROLE_DESCRIPTIONS.iteritems()
              },
          )
        ],
    )


def create_routes(): # pragma: no cover
  """Instantiates a pRPC server and returns webapp2 routes for it."""
  server = prpc.Server()
  server.add_service(AccessServicer())
  return server.get_routes()
