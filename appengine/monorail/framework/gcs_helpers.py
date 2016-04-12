# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Set of helpers for interacting with Google Cloud Storage."""

import base64
import logging
import os
import time
import urllib
import uuid

from datetime import datetime, timedelta

from google.appengine.api import app_identity
from google.appengine.api import images
from third_party import cloudstorage

from framework import filecontent


ATTACHMENT_TTL = timedelta(seconds=30)

IS_DEV_APPSERVER = (
    'development' in os.environ.get('SERVER_SOFTWARE', '').lower())

RESIZABLE_MIME_TYPES = ['image/png', 'image/jpg', 'image/jpeg', 'image/gif']

DEFAULT_THUMB_WIDTH = 250
DEFAULT_THUMB_HEIGHT = 200
LOGO_THUMB_WIDTH = 110
LOGO_THUMB_HEIGHT = 30


def _Now():
  return datetime.utcnow()


class UnsupportedMimeType(Exception):
  pass


def DeleteObjectFromGCS(object_id):
  object_path = ('/' + app_identity.get_default_gcs_bucket_name() + object_id)
  cloudstorage.delete(object_path)


def StoreObjectInGCS(
    content, mime_type, project_id, thumb_width=DEFAULT_THUMB_WIDTH,
    thumb_height=DEFAULT_THUMB_HEIGHT):
  bucket_name = app_identity.get_default_gcs_bucket_name()
  guid = uuid.uuid4()
  object_id = '/%s/attachments/%s' % (project_id, guid)
  object_path = '/' + bucket_name + object_id
  with cloudstorage.open(object_path, 'w', mime_type) as f:
    f.write(content)

  if mime_type in RESIZABLE_MIME_TYPES:
    # Create and save a thumbnail too.
    thumb_content = None
    try:
      thumb_content = images.resize(content, thumb_width, thumb_height)
    except Exception, e:
      # Do not raise exception for incorrectly formed images.
      # See https://bugs.chromium.org/p/monorail/issues/detail?id=597 for more
      # detail.
      logging.exception(e)
    if thumb_content:
      thumb_path = '%s-thumbnail' % object_path
      with cloudstorage.open(thumb_path, 'w', 'image/png') as f:
        f.write(thumb_content)

  return object_id


def CheckMimeTypeResizable(mime_type):
  if mime_type not in RESIZABLE_MIME_TYPES:
    raise UnsupportedMimeType(
        'Please upload a logo with one of the following mime types:\n%s' %
            ', '.join(RESIZABLE_MIME_TYPES))


def StoreLogoInGCS(file_name, content, project_id):
  mime_type = filecontent.GuessContentTypeFromFilename(file_name)
  CheckMimeTypeResizable(mime_type)
  if '\\' in file_name:  # IE insists on giving us the whole path.
    file_name = file_name[file_name.rindex('\\') + 1:]
  return StoreObjectInGCS(
      content, mime_type, project_id, thumb_width=LOGO_THUMB_WIDTH,
      thumb_height=LOGO_THUMB_HEIGHT)


def SignUrl(gcs_filename):
  expiration_dt = _Now() + ATTACHMENT_TTL
  expiration = int(time.mktime(expiration_dt.timetuple()))
  signature_string = '\n'.join([
      'GET',
      '',  # Optional MD5, which we don't have.
      '',  # Optional content-type, which only applies to uploads.
      str(expiration),
      gcs_filename]).encode('utf-8')

  signature_bytes = app_identity.sign_blob(signature_string)[1]

  query_params = {'GoogleAccessId': app_identity.get_service_account_name(),
                  'Expires': str(expiration),
                  'Signature': base64.b64encode(signature_bytes)}

  result = 'https://storage.googleapis.com{resource}?{querystring}'

  if IS_DEV_APPSERVER:
    result = '/_ah/gcs{resource}?{querystring}'

  return result.format(
        resource=gcs_filename, querystring=urllib.urlencode(query_params))

