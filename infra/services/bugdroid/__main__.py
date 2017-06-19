# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import base64
import collections
import datetime
import httplib2
import json
import logging
import os
import sys
import time
import urlparse

from infra.libs import git2
from infra.libs.service_utils import outer_loop
from infra_libs import logs
from infra_libs import ts_mon
from infra.services.bugdroid import bugdroid

import infra_libs
import oauth2client.client


DEFAULT_LOGGER = logging.getLogger(__name__)
DEFAULT_LOGGER.addHandler(logging.NullHandler())
DEFAULT_LOGGER.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
sh = logging.StreamHandler()
sh.setLevel(logging.DEBUG)
sh.setFormatter(formatter)
DEFAULT_LOGGER.addHandler(sh)

DIRBASE = os.path.splitext(os.path.basename(__file__))[0]
DATADIR = os.path.join(os.environ.get('HOME', ''), 'appdata', DIRBASE)

DATA_URL = 'https://bugdroid-data.appspot.com/_ah/api/bugdroid/v1/data'


def get_data(http):
  DEFAULT_LOGGER.info('Getting data files from gcs...')
  _, content = http.request(DATA_URL,
                            headers={'Content-Type': 'application/json'})
  data_json = json.loads(content)
  data_files = json.loads(data_json['data_files'])
  DEFAULT_LOGGER.info('Writing %d data files to %s', len(data_files), DATADIR)
  for data_file in data_files:
    content = base64.b64decode(data_file['file_content'])
    file_path = os.path.join(DATADIR, data_file['file_name'])
    with open(file_path, 'w') as fh:
      fh.write(content)


def update_data(http):
  DEFAULT_LOGGER.info('Updating data files to gcs...')
  result = []
  for data_file in os.listdir(DATADIR):
    if os.path.isdir(data_file):
      continue
    file_path = os.path.join(DATADIR, data_file)
    with open(file_path) as fh:
      result.append({
          'file_name': data_file,
          'file_content': base64.b64encode(fh.read()),
      })

  data_files = json.dumps(result)
  http.request(
      DATA_URL, 'POST', body=json.dumps({'data_files': data_files}),
      headers={'Content-Type': 'application/json'})


def parse_args(args):  # pragma: no cover
  parser = argparse.ArgumentParser('./run.py %s' % __package__)
  parser.add_argument('-c', '--configfile',
      help='Local JSON poller configuration file to override '
           'config file from luci-config.')
  parser.add_argument('-d', '--credentials_db', required=True,
      help='File to use for Monorail OAuth2 credentials storage.')
  parser.add_argument('--datadir', default=DATADIR,
      help='Directory where persistent app data should be stored.')

  logs.add_argparse_options(parser)
  ts_mon.add_argparse_options(parser)
  outer_loop.add_argparse_options(parser)

  parser.set_defaults(
      ts_mon_target_type='task',
      ts_mon_task_service_name='bugdroid',
      ts_mon_task_job_name='bugdroid_job'
  )
  opts = parser.parse_args(args)

  logs.process_argparse_options(opts)
  ts_mon.process_argparse_options(opts)
  loop_opts = outer_loop.process_argparse_options(opts)

  return opts, loop_opts


def _create_http(creds_data):
  credentials = oauth2client.client.OAuth2Credentials(
      None, creds_data['client_id'], creds_data['client_secret'],
      creds_data['refresh_token'],
      datetime.datetime.now() + datetime.timedelta(minutes=15),
      'https://accounts.google.com/o/oauth2/token',
      'bugdroid')

  http = infra_libs.InstrumentedHttp('gcs')
  http = infra_libs.RetriableHttp(http, retrying_statuses_fn=lambda x: x >= 400)
  http = credentials.authorize(http)
  return http


def main(args):  # pragma: no cover
  opts, loop_opts = parse_args(args)

  if not os.path.isdir(opts.datadir):
    DEFAULT_LOGGER.info('Creating data directory.')
    os.makedirs(opts.datadir)

  with open(opts.credentials_db) as data_file:
    creds_data = json.load(data_file)

  # Use local json file
  if not opts.configfile:
    get_data(_create_http(creds_data))

  def outer_loop_iteration():
    return bugdroid.inner_loop(opts)

  loop_results = outer_loop.loop(
      task=outer_loop_iteration,
      sleep_timeout=lambda: 60.0,
      **loop_opts)

  # In case local json file is used, do not upload
  if not opts.configfile:
    update_data(_create_http(creds_data))

  DEFAULT_LOGGER.info('Outer loop finished with result %r',
                      loop_results.success)

  return 0 if loop_results.success else 1


if __name__ == '__main__':  # pragma: no cover
  sys.exit(main(sys.argv[1:]))