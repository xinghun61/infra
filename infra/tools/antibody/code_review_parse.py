# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import requests
from simplejson.scanner import JSONDecodeError
import time

import infra.tools.antibody.cloudsql_connect as csql

# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


def extract_json_data(rietveld_url):  # pragma: no cover
  url_components = re.split('(https?:\/\/)([\da-z\.-]+)', rietveld_url)
  json_data_url = '%s%s/api%s?messages=true' %(url_components[1],
                  url_components[2], url_components[3])
  response = requests.get(json_data_url)
  if (response.status_code == requests.codes.ok):
    try:
      return response.json()
    except JSONDecodeError:
      LOGGER.error('json parse failed for url: %s' % rietveld_url)
      raise
  else:
    response.raise_for_status()


def contains_lgtm(json_data):
  for message in json_data['messages']:
    if message['approval']:
      return True
  return False


def contains_tbr(json_data):
  description = json_data['description']
  return any(
        not line.strip().startswith('>') and re.search(r'^TBR=.*', line)
        for line in description.splitlines())


def to_canonical_rietveld_url(rietveld_url):
  if 'chromiumcodereview.appspot.com' in rietveld_url:
    return rietveld_url.replace('chromiumcodereview.appspot.com',
                                'codereview.chromium.org') 
  if 'chromiumcodereview-hr.appspot.com' in rietveld_url:
    return rietveld_url.replace('chromiumcodereview-hr.appspot.com', 
                                'codereview.chromium.org')
  return rietveld_url


def add_rietveld_data_to_db(git_hash, rietveld_url, cc):  # pragma: no cover
  rietveld_url = to_canonical_rietveld_url(rietveld_url)
  try:
    json_data = extract_json_data(rietveld_url)
    db_data = (git_hash, contains_lgtm(json_data), contains_tbr(json_data),
               rietveld_url, time.time(), len(json_data['cc']))
    csql.write_to_rietveld_table(cc, db_data)
  except JSONDecodeError:
    pass


def get_tbr_no_lgtm(cc):
  cc.execute('SELECT * FROM rietveld')
  db_data = cc.fetchall()
  suspicious_commits = []
  # db_data: (git_hash, lgtm, tbr, rietveld_url, request_timestamp, num_cced)
  for line in db_data:
    lgtm, tbr = line[1:3]
    if lgtm == '0' and tbr == '1':
      suspicious_commits.append(line)
  return suspicious_commits