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
from oauth2client.client import OAuth2Credentials


DEFAULT_LOGGER = logging.getLogger(__name__)
DEFAULT_LOGGER.addHandler(logging.NullHandler())
DEFAULT_LOGGER.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
sh = logging.StreamHandler()
sh.setLevel(logging.DEBUG)
sh.setFormatter(formatter)
DEFAULT_LOGGER.addHandler(sh)

# TODO(sheyang): move to cloud
DIRBASE = os.path.splitext(os.path.basename(__file__))[0]
DATADIR = os.path.join(os.environ.get('HOME', ''), 'appdata', DIRBASE)


DATA_URL = 'https://bugdroid-data.appspot.com/_ah/api/bugdroid/v1/data'


def get_data(http):
  DEFAULT_LOGGER.info('Getting data from datastore...')
  retry_count = 5
  success = False
  for i in xrange(retry_count):
    resp, content = http.request(DATA_URL,
                                 headers={'Content-Type':'application/json'})
    if resp.status >= 400:
      DEFAULT_LOGGER.warning('Failed to get data in retry %d. Status: %d.',
                      i, resp.status)
      time.sleep(i)
      continue
    data_json = json.loads(content)
    data_files = json.loads(data_json['data_files'])
    for data_file in data_files:
      content = base64.b64decode(data_file['file_content'])
      file_path = os.path.join(DATADIR, data_file['file_name'])

      # Bit map for gerrit
      if data_file['file_name'].endswith('.seen'):
        with open(file_path, "wb") as binary_file:
          binary_file.write(content)
      else:
        with open(file_path, "w") as text_file:
          text_file.write(content)
    success = True
    break
  return success


def update_data(http):
  DEFAULT_LOGGER.info('Updating data to datastore...')
  result = []
  for data_file in os.listdir(DATADIR):
    if os.path.isdir(data_file):
      continue
    DEFAULT_LOGGER.debug('Processing file %s', data_file)
    file_dict = {}
    file_dict['file_name'] = data_file
    file_path = os.path.join(DATADIR, data_file)
    # binary
    if data_file.endswith('.seen'):
      with open(file_path, "rb") as binary_file:
        file_dict['file_content'] = base64.b64encode(binary_file.read())
    else:
      with open(file_path, "r") as text_file:
        file_dict['file_content'] = base64.b64encode(text_file.read())
    result.append(file_dict)
    DEFAULT_LOGGER.debug('Completed file %s', data_file)

  DEFAULT_LOGGER.info('Creating json...')
  data_files = json.dumps(result)
  DEFAULT_LOGGER.info('Finish creating json...')
  retry_count = 5
  success = False
  for i in xrange(retry_count):
    DEFAULT_LOGGER.info('Sending post request %d...', i)
    resp, _ = http.request(
        DATA_URL, "POST", body=json.dumps({'data_files': data_files}),
        headers={'Content-Type': 'application/json'})
    DEFAULT_LOGGER.info('Post request %d status: %d', i, resp.status)
    if resp.status >= 400:
      DEFAULT_LOGGER.warning('Failed to update data in retry %d. Status: %d.',
                      i, resp.status)
      time.sleep(i)
      continue
    success = True
    break
  return success


def parse_args(args):  # pragma: no cover
  parser = argparse.ArgumentParser('./run.py %s' % __package__)
  parser.add_argument('-c', '--configfile',
                 help='Local JSON poller configuration file to override '
                      'confilg file from luci-config.')
  parser.add_argument('-d', '--credentials_db',
                 help='File to use for Codesite OAuth2 credentials storage.')
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


def main(args):  # pragma: no cover
  opts, loop_opts = parse_args(args)

  with open(opts.credentials_db) as data_file:    
    creds_data = json.load(data_file)

  credentials = OAuth2Credentials(
      None, creds_data['client_id'], creds_data['client_secret'],
      creds_data['refresh_token'],
      datetime.datetime.now() + datetime.timedelta(minutes=15),
      'https://accounts.google.com/o/oauth2/token',
      'python-issue-tracker-manager/2.0')
  http = httplib2.Http()
  http = credentials.authorize(http)

  if not get_data(http):
    DEFAULT_LOGGER.error('Failed to get data files.')
    return 1

  DEFAULT_LOGGER.debug('Attemp to post again...')
  update_data(http)
  DEFAULT_LOGGER.debug('Attemp to post again completed...')

  def outer_loop_iteration():
    return bugdroid.inner_loop(opts)

  loop_results = outer_loop.loop(
      task=outer_loop_iteration,
      sleep_timeout=lambda: 5.0,
      **loop_opts)

  if not update_data(http):
    DEFAULT_LOGGER.error('Failed to update data files.')
    return 1

  DEFAULT_LOGGER.info('Outer loop finished with result %r',
                      loop_results.success)

  return 0 if loop_results.success else 1


if __name__ == '__main__':  # pragma: no cover
  sys.exit(main(sys.argv[1:]))