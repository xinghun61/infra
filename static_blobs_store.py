# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Serve static images."""

import logging
import urllib

from google.appengine.api import memcache
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import blobstore_handlers

import base_page


VALID_RESOURCES = [ 'favicon.ico', 'logo.png' ]


class StaticBlobStoreFile(db.Model):
  """A reference to a static blob to serve."""
  blob = blobstore.BlobReferenceProperty(required=True)
  # The corresponding file name of this object. blob.filename contains the
  # original file name.
  filename = db.StringProperty(required=True)


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
  """Uploads a static file."""
  def post(self, resource):
    resource = str(urllib.unquote(resource))
    if not resource in VALID_RESOURCES:
      logging.warning('Unknown resource "%s"' % resource)
      self.error(404)
    upload_files = self.get_uploads('file')
    blob_info = upload_files[0]
    blob = StaticBlobStoreFile.gql('WHERE filename = :1', resource).get()
    if blob:
      blob.blob = blob_info
    else:
      blob = StaticBlobStoreFile(blob=blob_info, filename=resource)
    blob.put()
    memcache.set(resource, blob_info.key(), namespace='static_blobs')
    self.redirect('/static_blobs/' + resource)


class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
  """Serves a static file."""
  def get(self, resource):
    filename = str(urllib.unquote(resource))
    if not filename in VALID_RESOURCES:
      logging.warning('Unknown resource "%s"' % resource)
      self.error(404)
    blob_key = memcache.get(filename, namespace='static_blobs')
    if blob_key is None:
      blob = StaticBlobStoreFile.gql('WHERE filename = :1', filename).get()
      if blob:
        blob_key = blob.blob
      else:
        # Cache negative.
        blob_key = ''
      memcache.set(filename, blob_key, namespace='static_blobs')
    if blob_key:
      self.send_blob(blob_key)
    else:
      self.redirect('/static/' + resource)


class FormPage(base_page.BasePage):
  """A simple form to upload a static blob."""
  def get(self, resource):
    (validated, is_admin) = self.ValidateUser()
    resource = str(urllib.unquote(resource))
    if not resource in VALID_RESOURCES:
      logging.warning('Unknown resource "%s"' % resource)
      self.error(404)
      return
    template_values = self.InitializeTemplate(self.app_name)
    template_values['upload_url'] = blobstore.create_upload_url(
        '/restricted/static_blobs/upload_internal/' + resource)
    template_values['is_admin'] = is_admin
    self.DisplayTemplate('static_blob_upload_form.html', template_values)


class ListPage(base_page.BasePage):
  """List the uploaded blobs."""
  def get(self):
    template_values = self.InitializeTemplate(self.app_name + ' static files')
    template_values['blobs'] = StaticBlobStoreFile.all()
    self.DisplayTemplate('static_blobs_store_list.html', template_values)
