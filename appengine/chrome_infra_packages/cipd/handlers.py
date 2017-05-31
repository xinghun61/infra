# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper handlers to support non-API clients."""

import webapp2

from components import auth

from . import acl
from . import client
from . import impl


class ClientHandler(auth.AuthenticatingHandler):
  """Redirects a caller to Google Storage URL with CIPD client binary.

  GET /client?platform=...&version=...

  Where:
    platform: linux-amd64, windows-386, etc.
    version: a package version identifier (instance ID, a ref or a tag).

  On success issues HTTP 302 redirect to Google Storage with the binary.
  On errors returns HTTP 4** with an error message.

  This is curl-friendly version of 'fetchClientBinary' Cloud Endpoints method
  that additionally does version resolution.
  """

  @auth.public  # auth inside
  def get(self):
    platform = self.request.get('platform')
    if not platform:
      self.abort(400, 'No "platform" specified.')
    version = self.request.get('version')
    if not version:
      self.abort(400, 'No "version" specified.')

    # Make sure params looks okay syntactically. Don't touch datastore yet.
    pkg = client.CIPD_CLIENT_PREFIX + platform
    if not impl.is_valid_package_path(pkg):
      self.abort(400, 'Invalid platform name.')
    if not client.is_cipd_client_package(pkg):
      self.abort(400, 'Unrecognized platform name.')
    if not impl.is_valid_instance_version(version):
      self.abort(400, 'Invalid version identifier.')

    # Client packages are usually public, but this is not hardcoded, check ACL.
    caller = auth.get_current_identity()
    if not acl.can_fetch_instance(pkg, caller):
      self.abort(403, 'Not allowed.')

    # The rest of the calls touch datastore and Google Storage, need
    # a configured Repo implementation.
    repo = impl.get_repo_service()
    if repo is None:
      self.abort(500, 'The service is not configured.')

    # Resolve a version to a concrete instance ID, if necessary.
    instance_id = version
    if not impl.is_valid_instance_id(version):
      ids = repo.resolve_version(pkg, version, limit=2)
      if not ids:
        self.abort(404, 'No such package.')
      if len(ids) > 1:
        self.abort(
          409, 'The provided tag points to multiple instances, can\'t use it '
          'as a version identifier.')
      instance_id = ids[0]

    # Fetch metadata of the instance, make sure it exists (it may not if
    # the version identifier was given as an instance ID).
    instance = repo.get_instance(pkg, instance_id)
    if not instance:
      self.abort(404, 'No such package.')

    # This is "cipd.exe" on Windows or just "cipd" on other platforms, to use
    # in Content-Disposition header.
    exe_name = client.get_cipd_client_filename(pkg)

    # The client binary is extracted via separate process that could have failed
    # or still be running.
    client_info, err = repo.get_client_binary_info(instance, filename=exe_name)
    if err:
      self.abort(404, 'The client binary is not available. Error: %s.' % err)
    if not client_info:
      self.abort(404, 'The client binary is not extracted yet, try later.')

    # Success!
    self.redirect(client_info.fetch_url)


def get_frontend_routes():  # pragma: no cover
  """Returns a list of webapp2.Route to add to frontend WSGI app."""
  return [
    webapp2.Route(r'/client', ClientHandler),
  ]
