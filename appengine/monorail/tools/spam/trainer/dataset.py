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
LEGACY_CSV_COLUMNS = ['verdict', 'subject', 'content']


def from_file(f):
  rows = []
  skipped_rows = 0
  for row in csv.reader(f):
    if len(row) == len(CSV_COLUMNS):
      # Throw out email field
      rows.append(row[:3])
    elif len(row) == len(LEGACY_CSV_COLUMNS):
      rows.append(row)
    else:
      skipped_rows += 1

  return rows, skipped_rows


def fetch_training_data(bucket, prefix):
  training_data = []

  credentials = GoogleCredentials.get_application_default()
  storage = discovery.build('storage', 'v1', credentials=credentials)
  objects = storage.objects()

  request = objects.list(bucket=bucket, prefix=prefix)
  response = make_api_request(request)
  items = response.get('items')
  csv_filepaths = [blob.get('name') for blob in items]

  # Add code
  csv_filepaths = [
    'spam-training-data/full-android.csv',
    'spam-training-data/full-support.csv',
  ] + csv_filepaths

  for filepath in csv_filepaths:
    rows, skipped_rows = fetch_training_csv(filepath, objects, bucket)

    if len(rows):
      training_data.extend(rows)

    tf.logging.info('{:<40}{:<20}{:<20}'.format(
      filepath,
      'added %d rows' % len(rows),
      'skipped %d rows' % skipped_rows))

  return training_data


def fetch_training_csv(filepath, objects, bucket):
  request = objects.get_media(bucket=bucket, object=filepath)
  media = make_api_request(request)
  return from_file(StringIO.StringIO(media))


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
      verdict, subject, content = row
      X.append(GenerateFeaturesRaw(str(subject), str(content),
        trainer.model.SPAM_FEATURE_HASHES))
      y.append(1 if verdict == 'spam' else 0)
  return X, y
