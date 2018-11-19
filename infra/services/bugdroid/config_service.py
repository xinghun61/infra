# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fetch repo configs."""

import base64
import httplib2
import json
import logging

from google.protobuf import text_format
from oauth2client.client import OAuth2Credentials

from infra.services.bugdroid.proto import repo_config_pb2


LUCI_CONFIG_URL = ('https://luci-config.appspot.com/_ah/api/config/v1/'
                   'config_sets/services%2Fbugdroid/config/'
                   'bugdroid_config.cfg')
DEFAULT_NO_MERGE_REFS = ['refs/heads/master', 'refs/heads/git-svn']


def get_repos(credentials_db, configfile=None):
  if configfile:
    logging.info('Read repo configs from local file %s', configfile)
    with open(configfile, 'r') as f:
      content_text = f.read()

  else:
    logging.info('Read repo configs from luci-config.')
    with open(credentials_db) as data_file:
      creds_data = json.load(data_file)
    credentials = OAuth2Credentials(
        None, creds_data['client_id'], creds_data['client_secret'],
        creds_data['refresh_token'], None,
        'https://accounts.google.com/o/oauth2/token',
        'bugdroid-config-service')
    if not credentials:
      logging.error('Invalid credentail file')
      return None

    http = httplib2.Http()
    http = credentials.authorize(http)
    headers={'Content-Type': 'application/json; charset=UTF-8'}
    resp, content = http.request(LUCI_CONFIG_URL, headers=headers)
    if resp.status != 200:
      logging.error('Invalid response from luci-config: %d', resp.status)
      return None
    content_json = json.loads(content)
    config_content = content_json['content']
    content_text = base64.b64decode(config_content)

  cfg = repo_config_pb2.RepoConfigs()
  text_format.Merge(content_text, cfg)
  for repo in cfg.repos:
    if not repo.no_merge_refs:
      repo.no_merge_refs.extend(DEFAULT_NO_MERGE_REFS)
  return cfg


def _decode_enum(enum_type, enum_val):
  desc = getattr(enum_type, 'DESCRIPTOR', None)
  if not desc:
    return None
  val = desc.values_by_number.get(enum_val)
  if val:
    return val.name
  return None


def decode_url_template(enum_val):
  return _decode_enum(repo_config_pb2.UrlTemplate, enum_val)


def decode_path_url_template(enum_val):
  return _decode_enum(repo_config_pb2.PathUrlTemplate, enum_val)


def decode_repo_type(enum_val):
  return _decode_enum(repo_config_pb2.RepoType, enum_val)
