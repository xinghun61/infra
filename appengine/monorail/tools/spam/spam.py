#!/usr/bin/env python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""
Spam classifier command line tools.

Use this command to submit predictions locally or to the model running
in production. See tools/spam/README.md for more context on training
and model operations.

Note that in order for this command to work, you must be logged into
gcloud in the project under which you wish to run commands.
"""

import argparse
import json
import os
import re
import sys
import googleapiclient

import spam_helpers

from apiclient.discovery import build
from oauth2client.client import GoogleCredentials

credentials = GoogleCredentials.get_application_default()

# This must be identical with settings.spam_feature_hashes.
SPAM_FEATURE_HASHES = 500

MODEL_NAME = 'spam_only_words'


def Predict(args):
  ml = googleapiclient.discovery.build('ml', 'v1', credentials=credentials)

  with open(args.summary) as f:
    summary = f.read()
  with open(args.content) as f:
    content = f.read()

  instance = spam_helpers.GenerateFeaturesRaw(summary, content,
    SPAM_FEATURE_HASHES)

  project_ID = 'projects/%s' % args.project
  full_model_name = '%s/models/%s' % (project_ID, MODEL_NAME)
  request = ml.projects().predict(name=full_model_name, body={
    'instances': [{'inputs': instance['word_hashes']}]
  })

  try:
    response = request.execute()
    print(response)
  except googleapiclient.errors.HttpError, err:
    print('There was an error. Check the details:')
    print(err._get_reason())


def LocalPredict(_):
  print('This will write /tmp/instances.json.')
  print('Then you can call:')
  print(('gcloud ml-engine local predict --json-instances /tmp/instances.json'
    ' --model-dir {model_dir}'))

  summary = raw_input('Summary: ')
  description = raw_input('Description: ')
  instance = spam_helpers.GenerateFeaturesRaw(summary, description,
    SPAM_FEATURE_HASHES)

  with open('/tmp/instances.json', 'w') as f:
    json.dump({'inputs': instance['word_hashes']}, f)


def main():
  if not credentials and 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
    print ('GOOGLE_APPLICATION_CREDENTIALS environment variable is not set. '
          'Exiting.')
    sys.exit(1)

  parser = argparse.ArgumentParser(description='Spam classifier utilities.')
  parser.add_argument('--project', '-p', default='monorail-staging')
  subparsers = parser.add_subparsers(dest='command')

  predict = subparsers.add_parser('predict',
    help='Submit a prediction to the default model in ML Engine.')
  predict.add_argument('--summary', help='A file containing the summary.')
  predict.add_argument('--content', help='A file containing the content.')

  subparsers.add_parser('local-predict',
    help='Create an instance on the local filesystem to use in prediction.')

  args = parser.parse_args()

  cmds = {
    'predict':  Predict,
    'local-predict':  LocalPredict,
  }
  res = cmds[args.command](args)

  print json.dumps(res, indent=2)


if __name__ == '__main__':
  main()
