#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""
Component classifier command line tools.

Use this command to submit predictions to the model running
in production.

Note that in order for this command to work, you must be logged into
gcloud in the project under which you wish to run commands.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import argparse
import json
import os
import re
import sys

import googleapiclient
from googleapiclient import discovery
from googleapiclient import errors
from google.cloud.storage import client, bucket, blob
from apiclient.discovery import build
from oauth2client.client import GoogleCredentials

import ml_helpers

credentials = GoogleCredentials.get_application_default()

# This must be identical with settings.component_features.
COMPONENT_FEATURES = 5000

MODEL_NAME = 'component_top_words'


def Predict(args):
  ml = googleapiclient.discovery.build('ml', 'v1', credentials=credentials)

  with open(args.content) as f:
    content = f.read()

  project_ID = 'projects/%s' % args.project
  full_model_name = '%s/models/%s' % (project_ID, MODEL_NAME)
  model_request = ml.projects().models().get(name=full_model_name)
  model_response = model_request.execute()

  version_name = model_response['defaultVersion']['name']

  model_name = 'component_trainer_' + re.search("v_(\d+)",
                                                version_name).group(1)

  client_obj = client.Client(project=args.project)
  bucket_name = '%s-mlengine' % args.project
  bucket_obj = bucket.Bucket(client_obj, bucket_name)

  instance = ml_helpers.GenerateFeaturesRaw([content],
                                            COMPONENT_FEATURES,
                                            getTopWords(bucket_name,
                                                        model_name))


  request = ml.projects().predict(name=full_model_name, body={
    'instances': [{'inputs': instance['word_features']}]
  })

  try:
    response = request.execute()


    bucket_obj.blob = blob.Blob('%s/component_index.json'
                                % model_name, bucket_obj)
    component_index = bucket_obj.blob.download_as_string()
    component_index_dict = json.loads(component_index)

    return read_indexes(response, component_index_dict)

  except googleapiclient.errors.HttpError, err:
    print('There was an error. Check the details:')
    print(err._get_reason())


def getTopWords(bucket_name, model_name):
  storage = discovery.build('storage', 'v1', credentials=credentials)
  objects = storage.objects()

  request = objects.get_media(bucket=bucket_name,
                              object=model_name + '/topwords.txt')
  response = request.execute()

  top_list = response.split()
  top_words = {}
  for i in range(len(top_list)):
    top_words[top_list[i]] = i

  return top_words


def read_indexes(response, component_index):

  scores = response['predictions'][0]['scores']
  highest = scores.index(max(scores))

  component_id = component_index[str(highest)]

  return "Most likely component: index %d, component id %d" % (
      int(highest), int(component_id))


def main():
  if not credentials and 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
    print(('GOOGLE_APPLICATION_CREDENTIALS environment variable is not set. '
          'Exiting.'))
    sys.exit(1)

  parser = argparse.ArgumentParser(
      description='Component classifier utilities.')
  parser.add_argument('--project', '-p', default='monorail-staging')

  parser.add_argument('--content', '-c', required=True,
                      help='A file containing the content.')

  args = parser.parse_args()

  res = Predict(args)

  print(res)


if __name__ == '__main__':
  main()
