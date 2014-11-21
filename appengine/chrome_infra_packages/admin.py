# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Administration API accessible only by service admins.

Defined as Endpoints API mostly to abuse API Explorer UI and not to write our
own admin UI. Note that all methods are publicly visible (though the source code
itself is also publicly visible, so not a big deal).

Callers have to be in 'administrators' group.
"""

# Pylint doesn't like endpoints.
# pylint: disable=C0322,R0201

import cloudstorage
import endpoints
import logging

from protorpc import message_types
from protorpc import messages
from protorpc import remote

from components import auth

import config

# This is used by endpoints indirectly.
package = 'cipd'


class ServiceAccountInfo(messages.Message):
  """Identity and private key of a service account to use to sign GS URLs.

  For copy-pasting pleasure in API Explorer it's compatible with JSON blob
  produced by "Generate new JSON key" button in Cloud Console > APIs & auth >
  Credentials > Service Account.
  """
  client_email = messages.StringField(1, required=True)
  private_key = messages.StringField(2, required=True)
  private_key_id = messages.StringField(3, required=True)


class GoogleStorageConfig(messages.Message):
  """Google Storage paths to use for CAS."""
  cas_gs_path = messages.StringField(1, required=True)
  cas_gs_temp = messages.StringField(2, required=True)


@auth.endpoints_api(
    name='admin',
    version='v1',
    title='Administration API')
class AdminApi(remote.Service):
  """Administration API accessibly only by the service admins."""

  @auth.endpoints_method(ServiceAccountInfo, name='setServiceAccount')
  @auth.require(auth.is_admin)
  def service_account(self, request):
    """Changes service account email and private key used to sign GS URLs."""
    conf = config.GlobalConfig.fetch()
    if not conf:
      conf = config.GlobalConfig()

    changed = conf.modify(
        service_account_email=request.client_email,
        service_account_pkey=request.private_key,
        service_account_pkey_id=request.private_key_id)
    if changed:
      logging.warning('Updated service account configuration')

    return message_types.VoidMessage()

  @auth.endpoints_method(GoogleStorageConfig, name='setGoogleStorageConfig')
  @auth.require(auth.is_admin)
  def gs_config(self, request):
    """Configures paths in Google Storage to use by CAS service."""
    try:
      cloudstorage.validate_file_path(request.cas_gs_path.rstrip('/'))
      cloudstorage.validate_file_path(request.cas_gs_temp.rstrip('/'))
    except ValueError as err:
      raise endpoints.BadRequestException('Not a valid GS path: %s' % err)

    conf = config.GlobalConfig.fetch()
    if not conf:
      conf = config.GlobalConfig()

    changed = conf.modify(
        cas_gs_path=request.cas_gs_path.rstrip('/'),
        cas_gs_temp=request.cas_gs_temp.rstrip('/'))
    if changed:
      logging.warning('Updated Google Storage paths configuration')

    return message_types.VoidMessage()
