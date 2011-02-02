# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Serve static images."""

import logging
import urllib

from google.appengine.api import mail
from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.ext import webapp

import base_page


VALID_RESOURCES = [ 'favicon.ico', 'logo.png' ]


class StaticBlobInlineFile(db.Model):
  """A reference to a static blob to serve."""
  blob = db.BlobProperty(required=True)
  filename = db.StringProperty(required=True)
  original_filename = db.StringProperty(required=True)
  size = db.IntegerProperty(required=True)
  creation = db.DateTimeProperty(required=True, auto_now=True)


class UploadHandler(webapp.RequestHandler):
  """Uploads a static file."""
  def post(self, resource):
    # Module 'google.appengine.api.memcache' has no 'get' member
    # pylint: disable=E1101
    resource = str(urllib.unquote(resource))
    if not resource in VALID_RESOURCES:
      logging.warning('Unknown resource "%s"' % resource)
      self.error(404)
    upload_file = self.request.POST['file']
    blob_data = upload_file.value
    blob = StaticBlobInlineFile.gql('WHERE filename = :1', resource).get()
    if blob:
      blob.blob = blob_data
      blob.size = len(blob_data)
      blob.original_filename = upload_file.filename
    else:
      blob = StaticBlobInlineFile(blob=blob_data, filename=resource,
          original_filename=upload_file.filename, size=len(blob_data))
    blob.put()
    memcache.set(resource, blob_data, namespace='static_blobs')
    self.redirect('/static_blobs/' + resource)


class ServeHandler(webapp.RequestHandler):
  """Serves a static file."""
  def get(self, resource):
    # Module 'google.appengine.api.memcache' has no 'get' member
    # pylint: disable=E1101
    filename = str(urllib.unquote(resource))
    if not filename in VALID_RESOURCES:
      logging.warning('Unknown resource "%s"' % resource)
      self.error(404)
    blob_data = memcache.get(filename, namespace='static_blobs')
    if blob_data is None:
      blob = StaticBlobInlineFile.gql('WHERE filename = :1', filename).get()
      if blob:
        blob_data = blob.blob
      else:
        # Cache negative.
        blob_data = ''
      memcache.set(filename, blob_data, namespace='static_blobs')
    if blob_data:
      # Access to a protected member XXX of a client class
      # pylint: disable=W0212
      self.response.headers['Content-Type'] = mail._GetMimeType(filename)
      self.response.out.write(blob_data)
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
    template_values['upload_url'] = (
        '/restricted/static_blobs/upload_internal/' + resource)
    template_values['is_admin'] = is_admin
    self.DisplayTemplate('static_blob_upload_form.html', template_values)


class ListPage(base_page.BasePage):
  """List the uploaded blobs."""
  def get(self):
    template_values = self.InitializeTemplate(self.app_name + ' static files')
    template_values['blobs'] = StaticBlobInlineFile.all()
    self.DisplayTemplate('static_blobs_inline_list.html', template_values)
