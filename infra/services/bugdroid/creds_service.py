# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from infra_libs import luci_auth
from oauth2client.client import OAuth2Credentials


def get_credentials(credentials_db, user_agent, token_expiry=None):
  if luci_auth.available():
    return luci_auth.LUCICredentials()
  with open(credentials_db) as data_file:
    creds_data = json.load(data_file)
  return OAuth2Credentials(
      None, creds_data['client_id'], creds_data['client_secret'],
      creds_data['refresh_token'], token_expiry,
      'https://accounts.google.com/o/oauth2/token', user_agent)
