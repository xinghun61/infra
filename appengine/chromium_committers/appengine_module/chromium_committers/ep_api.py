# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file handles cloud endpoint configuration and logic."""

import logging

import endpoints
from protorpc import messages, message_types, remote

from appengine_module.chromium_committers import auth_util
from appengine_module.chromium_committers import committers


CLIENT_IDS = endpoints.users_id_token.SKIP_CLIENT_ID_CHECK

SCOPES = [
    endpoints.EMAIL_SCOPE,
]


@endpoints.api(name='committers', version='v1',
               allowed_client_ids=CLIENT_IDS, scopes=SCOPES,
               auth_level=endpoints.AUTH_LEVEL.REQUIRED,
               description='Committers List manipulation API.')
class CommittersApi(remote.Service):

  GetListResourceContainer = endpoints.ResourceContainer(
      message_types.VoidMessage,
      list_name=messages.StringField(1, required=True),
  )

  class GetListResponse(messages.Message):
    class Entry(messages.Message):
      email = messages.StringField(1)
    entries = messages.MessageField(Entry, 1, repeated=True)

  @endpoints.method(GetListResourceContainer, GetListResponse,
                    path='list/{list_name}', http_method='GET',
                    name='list.get')
  def get(self, request):
    user = auth_util.User.from_endpoints()
    try:
      l = committers.get_list(user, request.list_name)
    except (committers.AuthorizationError, committers.InvalidList) as e:
      logging.warning('Request not authorized: %s', e.message)
      raise endpoints.NotFoundException()

    emails = l.emails if l else ()
    return self.GetListResponse(
        entries=[self.GetListResponse.Entry(email=email)
                 for email in emails],
    )
