# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from api import monorail_servicer
from api.api_proto import users_pb2
from api.api_proto import users_prpc_pb2


class UsersServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to User objects.

  Each API request is implemented with a one-line "Run" method that matches
  the method defined in the .proto file, and a Do* method that:
  does any request-specific validation, uses work_env to safely operate on
  business objects, and returns a response proto.
  """

  DESCRIPTION = users_prpc_pb2.UsersServiceDescription

  def GetUser(self, request, prpc_context, cnxn=None, auth=None):
    return self.Run(self.DoGetUser, request, prpc_context,
                    cnxn=cnxn, auth=auth)

  def DoGetUser(self, _mc, request):
    # Do any request-specific validation:
    # None.

    # Use work_env to safely operate on business objects.
    email = request.email
    hashed_email = hash(request.email)

    # Return a response proto.
    return users_pb2.User(
        email=email,
        id=hashed_email)
