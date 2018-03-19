# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from api.proto import users_pb2
from api.proto import users_prpc_pb2


class UsersServicer(object):
  """Handle API requests related to User objects.
  """

  DESCRIPTION = users_prpc_pb2.UsersServiceDescription

  def GetUser(self, request, _context):
    assert isinstance(request, users_pb2.GetUserRequest)
    assert request.email
    ret = users_pb2.User()
    ret.email = request.email
    ret.id = hash(request.email)
    return ret
