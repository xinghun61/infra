# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Main program for Bugdroid."""

import endpoints
import json
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


class BugdroidDataFile(messages.Message):
  """Base64-encoded data file for one repo."""
  file_content= messages.StringField(1)


DATAFILE_UPDATE_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    BugdroidDataFile,
    filename=messages.StringField(2, required=True)
)


DATAFILE_GET_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    # The request body should be empty.
    message_types.VoidMessage,
    filename=messages.StringField(1, required=True)
)


@endpoints.api(name='bugdroid', version='v1',
               description='bugdroid API to manage data configs.',
               allowed_client_ids=ALLOWED_CLIENT_IDS)
class BugdroidApi(remote.Service):  # pragma: no cover

  @endpoints.method(
      DATAFILE_GET_REQUEST_RESOURCE_CONTAINER,
      BugdroidDataFile,
      path='datafile/{filename}',
      http_method='GET',
      name='datafile.get')
  def datafile_get(self, request):
    bucket_name = app_identity.get_default_gcs_bucket_name()
    object_path = '/' + bucket_name + '/' + request.filename
    file_content = None
    try:
      with gcs.open(object_path) as f:
        file_content = f.read().decode('utf-8')
    except gcs.NotFoundError:
      raise endpoints.NotFoundException()
    if file_content:
      return BugdroidDataFile(file_content=file_content)
    else:
      raise endpoints.NotFoundException()

  @endpoints.method(
      DATAFILE_UPDATE_REQUEST_RESOURCE_CONTAINER,
      message_types.VoidMessage,
      path='datafile/{filename}',
      http_method='POST',
      name='datafile.update')
  def datafile_update(self, request):
    bucket_name = app_identity.get_default_gcs_bucket_name()
    object_path = '/' + bucket_name + '/' + request.filename
    with gcs.open(object_path, 'w') as f:
      f.write(request.file_content.encode('utf-8') )
    return message_types.VoidMessage()

  @endpoints.method(
      message_types.VoidMessage,
      BugdroidData,
      path='data',
      http_method='GET',
      name='data.get')
  def data_get(self, _):
    bucket_name = app_identity.get_default_gcs_bucket_name()
    object_path = '/' + bucket_name
    filestats = gcs.listbucket(object_path)
    if filestats:
      data_files = []
      for filestat in filestats:
        # Ignore dirs (although there really shouldn't be any).
        if filestat.is_dir:
          continue
        # Skip the old, consolidated data file (which should be deleted at some
        # point).
        if filestat.filename == '/'.join([object_path, ENTITY_KEY]):
          continue
        data_file = {'file_name': filestat.filename.split('/')[-1]}
        with gcs.open(filestat.filename) as f:
          data_file['file_content'] = f.read().decode('utf-8')
        data_files.append(data_file)
      if data_files:
        return BugdroidData(data_files=json.dumps(data_files))
      else:
        raise endpoints.NotFoundException()
    else:
      raise endpoints.NotFoundException()

  @endpoints.method(
      DATA_UPDATE_REQUEST_RESOURCE_CONTAINER,
      message_types.VoidMessage,
      path='data',
      http_method='POST',
      name='data.update')
  def data_update(self, _):
    return endpoints.InternalServerErrorException(
        'Bulk bugdroid data POST is obsolete due to excessive data size. '
        'See also crbug.com/880103.')


endpoint_list = endpoints_webapp2.api_server([BugdroidApi])
