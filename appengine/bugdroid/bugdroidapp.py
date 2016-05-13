# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Main program for Bugdroid."""

import endpoints
import logging

from endpoints import ResourceContainer
from google.appengine.ext import db
from protorpc import messages
from protorpc import message_types
from protorpc import remote


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


class BugdroidDataModel(db.Model):
  """Model for bugdroid data."""
  data_files = db.TextProperty()


@endpoints.api(name='bugdroid', version='v1',
               description='bugdroid API to manage data configs.',
               allowed_client_ids=ALLOWED_CLIENT_IDS)
class BugdroidApi(remote.Service):

  @endpoints.method(
      message_types.VoidMessage,
      BugdroidData,
      path='data',
      http_method='GET',
      name='data.get')
  def data_get(self, _):
    data = BugdroidDataModel.get_by_key_name(ENTITY_KEY)
    if data:
      return BugdroidData(data_files=data.data_files)
    else:
      raise endpoints.NotFoundException() 

  @endpoints.method(
      DATA_UPDATE_REQUEST_RESOURCE_CONTAINER,
      message_types.VoidMessage,
      path='data',
      http_method='POST',
      name='data.update')
  def data_update(self, request):
    logging.warning('data_files %s', request.data_files)
    data = BugdroidDataModel(data_files=request.data_files,
                             key_name=ENTITY_KEY)
    data.put()
    return message_types.VoidMessage()


endpoint_list = endpoints.api_server([BugdroidApi])