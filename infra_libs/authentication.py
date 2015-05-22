# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides means of authenticating http requests."""

import json
import logging
import os

import httplib2
import oauth2client.client

DEFAULT_SCOPES = ['email']

# This is part of the API.
# TODO: this is linux-specific, make it multi-platform.
SERVICE_ACCOUNTS_CREDS_ROOT = '/creds/service_accounts'


class AuthError(Exception):
  pass


def load_service_account_credentials(credentials_filename,
                                     service_accounts_creds_root=None):
  """Loads and validate a credential JSON file.

  Example of a well-formatted file:
    {
      "private_key_id": "4168d274cdc7a1eaef1c59f5b34bdf255",
      "private_key": ("-----BEGIN PRIVATE KEY-----\nMIIhkiG9w0BAQEFAASCAmEwsd"
                      "sdfsfFd\ngfxFChctlOdTNm2Wrr919Nx9q+sPV5ibyaQt5Dgn89fKV"
                      "jftrO3AMDS3sMjaE4Ib\nZwJgy90wwBbMT7/YOzCgf5PZfivUe8KkB"
                      -----END PRIVATE KEY-----\n",
      "client_email": "234243-rjstu8hi95iglc8at3@developer.gserviceaccount.com",
      "client_id": "234243-rjstu8hi95iglc8at3.apps.googleusercontent.com",
      "type": "service_account"
    }

  Args:
    credentials_filename (str): path to a .json file containing credentials
      for a Cloud platform service account.

  Keyword Args:
    service_accounts_creds_root (str or None): location where all service
      account credentials are stored. ``credentials_filename`` is relative
      to this path. None means 'use default location'.

  Raises:
    AuthError: if the file content is invalid.
  """
  service_accounts_creds_root = (service_accounts_creds_root
                                 or SERVICE_ACCOUNTS_CREDS_ROOT)

  service_account_file = os.path.join(service_accounts_creds_root,
                                      credentials_filename)
  try:
    with open(service_account_file, 'r') as f:
      key = json.load(f)
  except ValueError as e:
    raise AuthError('Parsing of file as JSON failed (%s): %s',
                    e, service_account_file)

  if key.get('type') != 'service_account':
    msg = ('Credentials type must be for a service_account, got %s.'
           ' Check content of %s' % (key.get('type'), service_account_file))
    logging.error(msg)
    raise AuthError(msg)

  if not key.get('client_email'):
    msg = ('client_email field missing in credentials json file. '
           ' Check content of %s' % service_account_file)
    logging.error(msg)
    raise AuthError(msg)

  if not key.get('private_key'):
    msg = ('private_key field missing in credentials json. '
           ' Check content of %s' % service_account_file)
    logging.error(msg)
    raise AuthError(msg)

  return key


def get_signed_jwt_assertion_credentials(credentials_filename,
                                         scope=None,
                                         service_accounts_creds_root=None):
  """Factory for SignedJwtAssertionCredentials

  Reads and validate the json credential file.

  Args:
    credentials_filename (str): path to the service account key file.
      See load_service_account_credentials() docstring for the file format.

  Keyword Args:
    scope (str|list of str): scope(s) of the credentials being
      requested. Defaults to https://www.googleapis.com/auth/userinfo.email.
    service_accounts_creds_root (str or None): location where all service
      account credentials are stored. ``credentials_filename`` is relative
      to this path. None means 'use default location'.
  """
  scope = scope or DEFAULT_SCOPES
  if isinstance(scope, basestring):
    scope = [scope]
  assert all(isinstance(s, basestring) for s in scope)

  key = load_service_account_credentials(
    credentials_filename,
    service_accounts_creds_root=service_accounts_creds_root)

  return oauth2client.client.SignedJwtAssertionCredentials(
    key['client_email'], key['private_key'], scope)


def get_authenticated_http(credentials_filename,
                           scope=None,
                           service_accounts_creds_root=None):
  """Creates an httplib2.Http wrapped with a service account authenticator.

  Args:
    credentials_filename (str): relative path to the file containing
      credentials in json format. Path is relative to the default
      location where credentials are stored (platform-dependent).

  Keyword Args:
    scope (str|list of str): scope(s) of the credentials being
      requested. Defaults to https://www.googleapis.com/auth/userinfo.email.
    service_accounts_creds_root (str or None): location where all service
      account credentials are stored. ``credentials_filename`` is relative
      to this path. None means 'use default location'.

  Returns:
    httplib2.Http authenticated with master's service account.
  """
  creds = get_signed_jwt_assertion_credentials(
    credentials_filename,
    scope=scope,
    service_accounts_creds_root=service_accounts_creds_root)

  return creds.authorize(httplib2.Http())
