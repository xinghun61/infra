# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import csv
import StringIO
import tensorflow as tf

from googleapiclient import discovery
from googleapiclient import errors
from oauth2client.client import GoogleCredentials

import trainer.model
from trainer.spam_helpers import GenerateFeaturesRaw


CSV_COLUMNS = ['verdict', 'subject', 'content', 'email']


def from_file(filename):
  rows = []
  skipped_rows = 0
  with open(filename) as f:
    for row in csv.reader(f):
      if len(row) != len(CSV_COLUMNS):
        skipped_rows += 1
        continue
      rows.append(row)

  if not rows:
    raise Exception('No training data found in CSV file: %s' % filename)

  if skipped_rows:
    tf.logging.warning('Skipped %d rows' % skipped_rows)

  return rows


def fetch_training_data(bucket, prefix):
  training_data = []

  credentials = GoogleCredentials.get_application_default()
  storage = discovery.build('storage', 'v1', credentials=credentials)
  objects = storage.objects()

  request = objects.list(bucket=bucket, prefix=prefix)
  response = make_api_request(request)
  items = response.get('items')
  csv_filepaths = [blob.get('name') for blob in items]

  for filepath in csv_filepaths:
    training_data.extend(fetch_training_csv(filepath, objects, bucket))

  return training_data


def fetch_training_csv(filepath, objects, bucket):
  tf.logging.info('Fetching CSV: %s' % filepath)
  request = objects.get_media(bucket=bucket, object=filepath)
  media = make_api_request(request)
  rows = []
  skipped_rows = 0

  for row in csv.reader(StringIO.StringIO(media)):
    if len(row) != len(CSV_COLUMNS):
      skipped_rows += 1
      continue
    rows.append(row)

  if skipped_rows:
    tf.logging.warning('Skipped %d rows' % skipped_rows)
  if len(rows):
    tf.logging.info('Appending %d training rows' % len(rows))

  return rows


def make_api_request(request):
  try:
    return request.execute()
  except errors.HttpError, err:
    tf.logging.error('There was an error with the API. Details:')
    tf.logging.error(err._get_reason())
    raise


def transform_csv_to_features(csv_training_data):
  X = []
  y = []
  for row in csv_training_data:
      verdict, subject, content, _ = row
      X.append(GenerateFeaturesRaw(str(subject), str(content),
        trainer.model.SPAM_FEATURE_HASHES))
      y.append(1 if verdict == 'spam' else 0)
  return X, y
