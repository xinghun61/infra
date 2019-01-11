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
from infra.services.bugdroid import bugdroid
from infra.services.bugdroid import creds_service
from infra_libs import logs
from infra_libs import ts_mon

import infra_libs
import oauth2client.client


DIRBASE = os.path.splitext(os.path.basename(__file__))[0]
DATADIR = os.path.join(os.environ.get('HOME', ''), 'appdata', DIRBASE)

BASE_URL = 'https://bugdroid-data.appspot.com/_ah/api/bugdroid/v1'
DATA_URL = '/'.join([BASE_URL, 'data'])
DATAFILE_URL = '/'.join([BASE_URL, 'datafile'])


def get_data(http):
  logging.info('Getting data files from gcs...')
  _, content = http.request(DATA_URL,
                            headers={'Content-Type': 'application/json'})
  data_json = json.loads(content)
  data_files = json.loads(data_json['data_files'])
  logging.info('Writing %d data files to %s', len(data_files), DATADIR)
  for data_file in data_files:
    content = base64.b64decode(data_file['file_content'])
    file_path = os.path.join(DATADIR, data_file['file_name'])
    with open(file_path, 'w') as fh:
      fh.write(content)


def update_data(http):
  # TODO(crbug/880103): This will currently do about 60 separate uploads on
  # every run. Maybe try to determine which data files actually changed and only
  # upload those?
  logging.info('Updating data files to gcs...')
  for data_file in os.listdir(DATADIR):
    if os.path.isdir(data_file):
      continue
    file_path = os.path.join(DATADIR, data_file)
    with open(file_path) as fh:
      http.request(
          '/'.join([DATAFILE_URL, data_file]),
          'POST',
          body=json.dumps({'file_content': base64.b64encode(fh.read())}),
          headers={'Content-Type': 'application/json'})


def parse_args(args):  # pragma: no cover
  parser = argparse.ArgumentParser('./run.py %s' % __package__)
  parser.add_argument('-c', '--configfile',
      help='Local JSON poller configuration file to override '
           'config file from luci-config.')
  parser.add_argument('-d', '--credentials_db',
      help='File to use for OAuth2 credentials storage if not running on LUCI.')
  parser.add_argument('--datadir', default=DATADIR,
      help='Directory where persistent app data should be stored.')
  parser.add_argument('--dryrun', action='store_true',
      help='Don\'t update monorail issues or update issues to the bugdroid '
           'appengine app.')

  logs.add_argparse_options(parser)
  ts_mon.add_argparse_options(parser)
  outer_loop.add_argparse_options(parser)

  parser.set_defaults(
      log_level=logging.DEBUG,
      ts_mon_target_type='task',
      ts_mon_task_service_name='bugdroid',
      ts_mon_task_job_name='bugdroid_job'
  )
  opts = parser.parse_args(args)

  logs.process_argparse_options(opts)
  ts_mon.process_argparse_options(opts)
  loop_opts = outer_loop.process_argparse_options(opts)

  # We need to include the logger ID (i.e. "%(name)s") in the formatter string.
  # Override the root logging handler set by infra_libs.logs.
  logging.root.handlers[0].setFormatter(logging.Formatter(
      '[%(severity)s%(iso8601)s %(process)d %(thread)d '
      '%(fullModuleName)s:%(lineno)s] (%(name)s) %(message)s'))

  return opts, loop_opts


def _create_http(credentials_db):
  token_expiry = datetime.datetime.now() + datetime.timedelta(minutes=15)
  credentials = creds_service.get_credentials(
      credentials_db, 'bugdroid', token_expiry=token_expiry)

  http = infra_libs.InstrumentedHttp('gcs')
  http = infra_libs.RetriableHttp(http, retrying_statuses_fn=lambda x: x >= 400)
  http = credentials.authorize(http)
  return http


def main(args):  # pragma: no cover
  opts, loop_opts = parse_args(args)

  if not os.path.isdir(opts.datadir):
    logging.info('Creating data directory.')
    os.makedirs(opts.datadir)

  # Use local json file
  if not opts.configfile:
    get_data(_create_http(opts.credentials_db))

  def outer_loop_iteration():
    return bugdroid.inner_loop(opts)

  loop_results = outer_loop.loop(
      task=outer_loop_iteration,
      sleep_timeout=lambda: 60.0,
      **loop_opts)

  # In case local json file is used, do not upload
  if not opts.configfile and not opts.dryrun:
    update_data(_create_http(opts.credentials_db))

  logging.info('Outer loop finished with result %r', loop_results.success)
  return 0 if loop_results.success else 1


if __name__ == '__main__':  # pragma: no cover
  sys.exit(main(sys.argv[1:]))
