# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from __future__ import absolute_import
from __future__ import division

import StringIO
import tensorflow as tf

from googleapiclient import discovery
from googleapiclient import errors
from oauth2client.client import GoogleCredentials

import trainer.model
import trainer.spam_helpers


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
  return trainer.spam_helpers.from_file(StringIO.StringIO(media))


def make_api_request(request):
  try:
    return request.execute()
  except errors.HttpError, err:
    tf.logging.error('There was an error with the API. Details:')
    tf.logging.error(err._get_reason())
    raise
