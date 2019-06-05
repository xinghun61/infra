# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import csv
import os
import re
import StringIO
import sys
import tensorflow as tf
import time

from googleapiclient import discovery
from googleapiclient import errors
from oauth2client.client import GoogleCredentials
import google
from google.cloud.storage import blob, bucket, client

import trainer.ml_helpers
import trainer.dataset


TOP_WORDS = 'topwords.txt'
STOP_WORDS = 'stopwords.txt'


def fetch_stop_words(project_id, objects):
  request = objects.get_media(bucket=project_id + '-mlengine',
                              object=STOP_WORDS)
  response = trainer.dataset.make_api_request(request)
  return response.split()


def fetch_training_csv(filepath, objects, b):
  request = objects.get_media(bucket=b, object=filepath)
  return trainer.dataset.make_api_request(request)


def GenerateTopWords(objects, word_dict, project_id):
  stop_words = fetch_stop_words(project_id, objects)
  sorted_words = sorted(word_dict, key=word_dict.get, reverse=True)

  top_words = []
  index = 0

  while len(top_words) < trainer.ml_helpers.COMPONENT_FEATURES:
    if sorted_words[index] not in stop_words:
      top_words.append(sorted_words[index])
    index += 1

  return top_words


def make_top_words_list(job_dir):
  """Returns the top (most common) words in the entire dataset for component
  prediction. If a file is already stored in GCS containing these words, the
  words from the file are simply returned. Otherwise, the most common words are
  determined and written to GCS, before being returned.

  Returns:
    A list of the most common words in the dataset (the number of them
    determined by ml_helpers.COMPONENT_FEATURES).
  """

  credentials = GoogleCredentials.get_application_default()
  storage = discovery.build('storage', 'v1', credentials=credentials)
  objects = storage.objects()

  subpaths = re.match('gs://(monorail-.*)-mlengine/(component_trainer_\d+)',
                      job_dir)

  if subpaths:
    project_id = subpaths.group(1)
    trainer_folder = subpaths.group(2)
  else:
    project_id = 'monorail-prod'

  storage_bucket = project_id + '.appspot.com'
  request = objects.list(bucket=storage_bucket,
                         prefix='component_training_data')

  response = trainer.dataset.make_api_request(request)

  items = response.get('items')
  csv_filepaths = [b.get('name') for b in items]

  final_string = ''

  for word in parse_words(csv_filepaths, objects, storage_bucket, project_id):
    final_string += word + '\n'

  if subpaths:
    client_obj = client.Client(project=project_id)
    bucket_obj = bucket.Bucket(client_obj, project_id + '-mlengine')

    bucket_obj.blob = google.cloud.storage.blob.Blob(trainer_folder
                                                   + '/'
                                                   + TOP_WORDS,
                                                   bucket_obj)
    bucket_obj.blob.upload_from_string(final_string,
                                       content_type='text/plain')
  return final_string.split()


def parse_words(files, objects, b, project_id):
  word_dict = {}

  csv.field_size_limit(sys.maxsize)
  for filepath in files:
    media = fetch_training_csv(filepath, objects, b)

    for row in csv.reader(StringIO.StringIO(media)):
      _, content = row
      words = content.split()

      for word in words:
        if word in word_dict:
          word_dict[word] += 1
        else:
          word_dict[word] = 1

  return GenerateTopWords(objects, word_dict, project_id)
