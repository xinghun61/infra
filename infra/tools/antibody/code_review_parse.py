# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import re
import requests
from simplejson.scanner import JSONDecodeError

import infra.tools.antibody.cloudsql_connect as csql

# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)

time_format = '%Y-%m-%d %H:%M:%S'


def extract_json_data(rietveld_url):  # pragma: no cover
  url_components = re.split('(https?:\/\/)([\da-z\.-]+)', rietveld_url)
  json_data_url = '%s%s/api%s?messages=true' % (url_components[1],
                  url_components[2], url_components[3])
  logging.info('Sending request to: %s', json_data_url)
  response = requests.get(json_data_url)
  if (response.status_code == requests.codes.ok):
    try:
      return response.json()
    except JSONDecodeError:
      LOGGER.error('json parse failed for url: %s' % rietveld_url)
      raise
  else:
    LOGGER.info('unable to access: %s' % rietveld_url)
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
  rietveld_url = rietveld_url.strip('.')
  if 'chromiumcodereview.appspot.com' in rietveld_url:
    return rietveld_url.replace('chromiumcodereview.appspot.com',
                                'codereview.chromium.org')
  if 'chromiumcodereview-hr.appspot.com' in rietveld_url:
    return rietveld_url.replace('chromiumcodereview-hr.appspot.com',
                                'codereview.chromium.org')
  return rietveld_url


def add_rietveld_data_to_review(rietveld_url, cc):  # pragma: no cover
  rietveld_url = to_canonical_rietveld_url(rietveld_url)
  try:
    db_data = get_rietveld_data_for_review(rietveld_url)
    csql.write_to_review(cc, db_data)
  except JSONDecodeError:
    pass


def get_rietveld_data_for_review(rietveld_url):
  json_data = extract_json_data(rietveld_url)
  curr_time = datetime.datetime.now()
  committed_timestamp = None
  patchset_still_exists = None
  for message in json_data['messages']:
    if ('committed' in message['text'].lower() and
        message['issue_was_closed']):
      committed_timestamp = message['date'].split('.')[0]
      if message['patchset'] in json_data['patchsets']:
        patchset_still_exists = True
      else:  # pragma: no cover
        patchset_still_exists = False
  db_data = (rietveld_url, curr_time, committed_timestamp,
             patchset_still_exists, None, None)
  return db_data


def add_rietveld_data_to_review_people(rietveld_url, cc):  # pragma: no cover
  try:
    db_data_all = get_rietveld_data_for_review_people(rietveld_url)
    csql.write_to_review_people(cc, db_data_all)
  except JSONDecodeError:
    pass


def get_rietveld_data_for_review_people(rietveld_url):
  rietveld_url = to_canonical_rietveld_url(rietveld_url)
  curr_time = datetime.datetime.now()
  db_data_all = []
  json_data = extract_json_data(rietveld_url)

  people = []
  people.append([json_data['cc'], 'cc'])
  people.append([json_data['reviewers'], 'reviewer'])
  people.append([[json_data['owner_email'],], 'owner'])
  time_submitted = json_data['created'].split('.')[0]
  for person_list, typ in people:
    for person in person_list:
      db_data = (person, rietveld_url, time_submitted, curr_time, typ)
      db_data_all.append(db_data)
  for message in json_data['messages']:
    if message['approval']:
      time_commented = message['date'].split('.')[0]
      db_data = (message['sender'], rietveld_url, time_commented, curr_time,
                 'lgtm')
      db_data_all.append(db_data)
    elif message['disapproval']:
      time_commented = message['date'].split('.')[0]
      db_data = (message['sender'], rietveld_url, time_commented, curr_time,
                'not lgtm')
      db_data_all.append(db_data)
  return db_data_all


def get_tbr_no_lgtm(cc, commit_people_type):  # pragma: no cover
  cc.execute("""SELECT review.review_url, git_commit.timestamp,
      git_commit.subject, commit_people.people_email_address, git_commit.hash
      FROM review
      INNER JOIN git_commit
      ON review.review_url = git_commit.review_url
      INNER JOIN commit_people
      ON commit_people.git_commit_hash = git_commit.hash
      LEFT JOIN (
        SELECT review_url, COUNT(*)
        AS c
        FROM review_people
        WHERE type = 'lgtm'
        GROUP BY review_url) lgtm_count
      ON review.review_url = lgtm_count.review_url
      WHERE lgtm_count.c = 0 OR lgtm_count.c IS NULL
      AND commit_people.type = '%s'""" % commit_people_type)
  data_all = cc.fetchall()
  formatted_data = []
  for data in data_all:
    subject = (data[2][:61] + '...') if len(data[2]) > 62 else data[2]
    formatted_data.append([data[0], data[1].strftime("%Y-%m-%d %H:%M:%S"),
                           subject.replace('-', ' '), data[3], data[4]])
  return sorted(formatted_data, key=lambda x: x[1], reverse=True)