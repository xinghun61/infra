# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Main program for Bugdroid."""

import endpoints
import logging
import os

import cloudstorage as gcs
from endpoints import ResourceContainer
from google.appengine.api import app_identity
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from components import endpoints_webapp2


ALLOWED_CLIENT_IDS = [
    endpoints.API_EXPLORER_CLIENT_ID,
    '768213250012.apps.googleusercontent.com']

ENTITY_KEY = 'bugdroid_data'


class BugdroidData(messages.Message):
  """Collection of repo data files."""
  data_files = messages.StringField(1)


DATA_UPDATE_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    BugdroidData,
)


@endpoints.api(name='bugdroid', version='v1',
               description='bugdroid API to manage data configs.',
               allowed_client_ids=ALLOWED_CLIENT_IDS)
class BugdroidApi(remote.Service):  # pragma: no cover

  @endpoints.method(
      message_types.VoidMessage,
      BugdroidData,
      path='data',
      http_method='GET',
      name='data.get')
  def data_get(self, _):
    bucket_name = app_identity.get_default_gcs_bucket_name()
    object_path = '/' + bucket_name + '/' + ENTITY_KEY
    data_files = None
    with gcs.open(object_path) as f:
      data_files = f.read()
      data_files = data_files.decode('utf-8')
    if data_files:
      return BugdroidData(data_files=data_files)
    else:
      raise endpoints.NotFoundException() 

  @endpoints.method(
      DATA_UPDATE_REQUEST_RESOURCE_CONTAINER,
      message_types.VoidMessage,
      path='data',
      http_method='POST',
      name='data.update')
  def data_update(self, request):
    bucket_name = app_identity.get_default_gcs_bucket_name()
    object_path = '/' + bucket_name + '/' + ENTITY_KEY
    with gcs.open(object_path, 'w') as f:
      f.write(request.data_files.encode('utf-8') )
    return message_types.VoidMessage()


endpoint_list = endpoints_webapp2.api_server([BugdroidApi])
