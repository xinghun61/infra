# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Cloud Endpoints API for CAS."""

# Pylint doesn't like endpoints.
# pylint: disable=C0322,R0201

from protorpc import message_types
from protorpc import messages
from protorpc import remote

from components import auth

# This is used by endpoints indirectly.
package = 'cipd'


class WhoResponse(messages.Message):
  identity = messages.StringField(1)


@auth.endpoints_api(name='cas_service', version='v1')
class CASServiceApi(remote.Service):
  """Content addressed store API."""

  # TODO: To be removed. Kept here just for the reference.
  @auth.endpoints_method(message_types.VoidMessage, WhoResponse)
  def who(self, _request):  # pragma: no cover
    return WhoResponse(identity=auth.get_current_identity().to_bytes())
