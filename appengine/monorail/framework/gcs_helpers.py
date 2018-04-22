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
from google.appengine.api import urlfetch
from third_party import cloudstorage
from third_party.cloudstorage import errors

from framework import filecontent
from framework import framework_constants


ATTACHMENT_TTL = timedelta(seconds=30)

IS_DEV_APPSERVER = (
    'development' in os.environ.get('SERVER_SOFTWARE', '').lower())

RESIZABLE_MIME_TYPES = [
    'image/png', 'image/jpg', 'image/jpeg', 'image/gif', 'image/webp',
    ]

DEFAULT_THUMB_WIDTH = 250
DEFAULT_THUMB_HEIGHT = 200
LOGO_THUMB_WIDTH = 110
LOGO_THUMB_HEIGHT = 30
MAX_ATTACH_SIZE_TO_COPY = 10 * 1024 * 1024  # 10 MB


def _Now():
  return datetime.utcnow()


class UnsupportedMimeType(Exception):
  pass


def DeleteObjectFromGCS(object_id):
  object_path = ('/' + app_identity.get_default_gcs_bucket_name() + object_id)
  cloudstorage.delete(object_path)


def StoreObjectInGCS(
    content, mime_type, project_id, thumb_width=DEFAULT_THUMB_WIDTH,
    thumb_height=DEFAULT_THUMB_HEIGHT, filename=None):
  bucket_name = app_identity.get_default_gcs_bucket_name()
  guid = uuid.uuid4()
  object_id = '/%s/attachments/%s' % (project_id, guid)
  object_path = '/' + bucket_name + object_id
  options = {}
  if filename:
    if not framework_constants.FILENAME_RE.match(filename):
      logging.info('bad file name: %s' % filename)
      filename = 'attachment.dat'
    options['Content-Disposition'] = 'inline; filename="%s"' % filename
  logging.info('Writing with options %r', options)
  with cloudstorage.open(object_path, 'w', mime_type, options=options) as f:
    f.write(content)

  if mime_type in RESIZABLE_MIME_TYPES:
    # Create and save a thumbnail too.
    thumb_content = None
    try:
      thumb_content = images.resize(content, thumb_width, thumb_height)
    except images.LargeImageError:
      # Don't log the whole exception because we don't need to see
      # this on the Cloud Error Reporting page.
      logging.info('Got LargeImageError on image with %d bytes', len(content))
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


def SignUrl(bucket, object_id):
  try:
    result = ('https://www.googleapis.com/storage/v1/b/'
        '{bucket}/o/{object_id}?access_token={token}&alt=media')

    if IS_DEV_APPSERVER:
      result = '/_ah/gcs{resource}?{querystring}'

    scopes = ['https://www.googleapis.com/auth/devstorage.read_only']

    if object_id[0] == '/':
      object_id = object_id[1:]

    url = result.format(
          bucket=bucket,
          object_id=urllib.quote_plus(object_id),
          token=app_identity.get_access_token(scopes)[0])

    resp = urlfetch.fetch(url, follow_redirects=False)

    redir = resp.headers["Location"]
    return redir

  except Exception as e:
    logging.exception(e)
    return '/missing-gcs-url'


def MaybeCreateDownload(bucket_name, object_id, filename):
  """If the obj is not huge, and no download version exists, create it."""
  src = '/%s%s' % (bucket_name, object_id)
  dst = '/%s%s-download' % (bucket_name, object_id)
  cloudstorage.validate_file_path(src)
  cloudstorage.validate_file_path(dst)
  logging.info('Maybe create %r from %r', dst, src)

  if IS_DEV_APPSERVER:
    logging.info('dev environment never makes download copies.')
    return False

  # If "Download" object already exists, we are done.
  try:
    cloudstorage.stat(dst)
    logging.info('Download version of attachment already exists')
    return True
  except errors.NotFoundError:
    pass

  # If "View" object is huge, give up.
  src_stat = cloudstorage.stat(src)
  if src_stat.st_size > MAX_ATTACH_SIZE_TO_COPY:
    logging.info('Download version of attachment would be too big')
    return False

  with cloudstorage.open(src, 'r') as infile:
    content = infile.read()
  logging.info('opened GCS object and read %r bytes', len(content))
  content_type = src_stat.content_type
  options = {
    'Content-Disposition': 'attachment; filename="%s"' % filename,
    }
  logging.info('Writing with options %r', options)
  with cloudstorage.open(dst, 'w', content_type, options=options) as outfile:
    outfile.write(content)
  logging.info('done writing')

  return True
