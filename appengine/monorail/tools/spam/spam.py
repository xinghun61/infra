#!/usr/bin/env python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""
Spam classifier command line tools.
Use this command to work with Monorail's Cloud Prediction API
Spam classifier models.

This presumes you already have some csv training data files present
in gcs and/or local disk, so run the training example exporter first
before trying to train or test models.

Example: The following command will report the training status of the
'android-user' model in the monorail-staging project:

spam.py -p monorail-staging -m android-user status

Note that in order for this command to work, you must have a service
account credentials file on your machine. Download one from Developer
Console -> Credentials -> [service account] -> Generate new JSON key.
"""

import argparse
import csv
import hashlib
import httplib2
import json
import logging
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import googleapiclient

from apiclient.discovery import build
from oauth2client.client import GoogleCredentials


credentials = GoogleCredentials.get_application_default()
service = build(
    'prediction', 'v1.6', http=httplib2.Http(), credentials=credentials)

def Status(args):
  result = service.trainedmodels().get(
      project=args.project,
      id=args.model,
  ).execute()
  return result

def List(args):
  result = service.trainedmodels().list(
      project=args.project,
  ).execute()
  return result

def Analyze(args):
  result = service.trainedmodels().analyze(
      project=args.project,
      id=args.model,
  ).execute()
  return result

def Train(args):
  result = service.trainedmodels().insert(
      project=args.project,
      body={'id':args.model, 'storageDataLocation': args.training_data}
  ).execute()
  return result

def _Classify(project, model, features):
  retries = 0
  while retries < 3:
    try:
      result = service.trainedmodels().predict(
          project=project,
          id=model,
          body={'input': {'csvInstance': features}}
      ).execute()
      return result
    except googleapiclient.errors.HttpError as err:
      retries = retries + 1
      print ('Error calling prediction API, attempt %d: %s' % (
          retries, sys.exc_info()[0]))
      print err.content.decode('utf-8')

  sys.exit(1)

  return result

def Test(args):
  with open(args.testing_data, 'rb') as csvfile:
    spamreader = csv.reader(csvfile)
    i = 0
    confusion = {"ham": {"ham": 0, "spam": 0}, "spam": {"ham": 0, "spam": 0}}
    for row in spamreader:
      i = i + 1
      if random.random() > args.sample_rate:
        continue
      label = row[0]
      features = row[1:]
      result = _Classify(args.project, args.model, features)
      c = confusion[label][result['outputLabel']]
      confusion[label][result['outputLabel']] = c + 1

      print "%d: actual: %s / predicted: %s" % (i, label, result['outputLabel'])

      if label != result['outputLabel']:
        print "Mismatch:"
        print json.dumps(row, indent=2)
        print json.dumps(result, indent=2)

    return confusion


class struct(dict):
  def __getattr__(self, key):
    return self.get(key)
  __setattr__ = dict.__setitem__
  __delattr__ = dict.__delitem__


def ROC(args):
  # See page 866, Algorithm 1 in
  # https://ccrma.stanford.edu/workshops/mir2009/references/ROCintro.pdf
  # Modified to also keep track of the threshold for point labels
  # when plotting the output.

  instances = []
  with open(args.testing_data, 'rb') as csvfile:
    spamreader = csv.reader(csvfile)
    total_negative, total_positive = 0.0, 0.0
    i = 0
    for row in spamreader:
      i = i + 1
      if random.random() > args.sample_rate:
        continue
      label = row[0]
      features = row[1:]
      result = _Classify(args.project, args.model, features)
      for p in result['outputMulti']:
        if p['label'] == 'spam':
          spam_score = float(p['score'])

      if label == 'spam':
        total_positive += 1
      else:
        total_negative += 1

      instances.append(struct(true_class=label, spam_score=spam_score))

  true_positive, false_positive = 0.0, 0.0
  results = []

  instances.sort(key=lambda i: 1.0 - i.spam_score)
  score_prev = None

  for i in instances:
    if score_prev is None or i.spam_score != score_prev:
      results.append(struct(
          x=false_positive/total_negative,
          y=true_positive/total_positive,
          threshold=i.spam_score))
      score_prev = i.spam_score

    if i.true_class == 'spam':
      true_positive += 1
    else:
      false_positive += 1

  results.append(struct(
      x=false_positive/total_negative,
      y=true_positive/total_positive,
      threshold=i.spam_score))

  print "False Positive Rate, True Positive Rate, Threshold"
  for r in results:
    print "%f, %f, %f" % (r.x, r.y, r.threshold)

  print "FP/N: %f/%f, TP/P: %f/%f" % (
      false_positive, total_negative, true_positive, total_positive)

def Prep(args):
  with open(args.infile, 'rb') as csvfile:
    with tempfile.NamedTemporaryFile('wb', delete=False) as trainfile:
      with open(args.test, 'wb') as testfile:
        for row in csvfile:
          # If hash features are requested, generate those instead of
          # the raw text.
          if args.hash_features > 0:
            row = row.split(',')
            # Hash every field after the first (which is the class)
            feature_hashes = _HashFeatures(row[1:], args.hash_features)
            # Convert to strings so we can re-join the columns.
            feature_hashes = [str(h) for h in feature_hashes]
            row = [row[0]]
            row.extend(feature_hashes)
            row = ','.join(row) + '\n'

          if random.random() > args.ratio:
            testfile.write(row)
          else:
            trainfile.write(row)

  print 'Copying %s to The Cloud as %s' % (trainfile.name, args.train)
  subprocess.check_call(['gsutil', 'cp', trainfile.name, args.train])

DELIMITERS = ['\s', '\,', '\.', '\?', '!', '\:', '\(', '\)']

def _HashFeatures(content, num_features):
  """
    Feature hashing is a fast and compact way to turn a string of text into a
    vector of feature values for classification and training.
    See also: https://en.wikipedia.org/wiki/Feature_hashing
    This is a simple implementation that doesn't try to minimize collisions
    or anything else fancy.
  """
  features = [0] * num_features
  for blob in content:
    words = re.split('|'.join(DELIMITERS), blob)
    for w in words:
      feature_index = int(int(hashlib.sha1(w).hexdigest(), 16) % num_features)
      features[feature_index] += 1

  return features

def main():
  if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
    print ('GOOGLE_APPLICATION_CREDENTIALS environment variable is not set. '
          'Exiting.')
    sys.exit(1)

  parser = argparse.ArgumentParser(
      description='Spam classifier utilities.')
  parser.add_argument('--project', '-p', default='monorail-staging')
  subparsers = parser.add_subparsers(dest='command')

  subparsers.add_parser('ls')

  parser_analyze = subparsers.add_parser('analyze')
  parser_analyze.add_argument('--model', '-m', required=True)

  parser_status = subparsers.add_parser('status')
  parser_status.add_argument('--model', '-m', required=True)

  parser_test = subparsers.add_parser('test')
  parser_test.add_argument('--model', '-m', required=True)
  parser_test.add_argument('--testing_data', '-x',
      help='Location of local testing csv file, e.g. /tmp/testing.csv')
  parser_test.add_argument('--sample_rate', '-r', default=0.01,
      help='Sample rate for classifier testing.')

  parser_roc = subparsers.add_parser('roc',
      help='Generate a Receiver Operating Characteristic curve')
  parser_roc.add_argument('--model', '-m', required=True)
  parser_roc.add_argument('--testing_data', '-x',
      help='Location of local testing csv file, e.g. /tmp/testing.csv')
  parser_roc.add_argument('--sample_rate', '-r', type=float, default=0.001,
      help='Sample rate for classifier testing.', )

  parser_train = subparsers.add_parser('train')
  parser_train.add_argument('--model', '-m', required=True)
  parser_train.add_argument('--training_data', '-t',
      help=('Location of training csv file (omit gs:// prefix), '
            'e.g. monorail-staging-spam-training-data/train.csv'))

  parser_prep = subparsers.add_parser('prep',
      help='Split a csv file into training and test')
  parser_prep.add_argument('--infile', '-i', required=True,
      help='CSV file with complete set of labeled examples.',)
  parser_prep.add_argument('--train', required=True,
      help=('Destination for training csv file, '
            'e.g. gs://monorail-staging-spam-training-data/train.csv'))
  parser_prep.add_argument('--test', required=True,
      help='Destination for training csv file, local filesystem.')
  parser_prep.add_argument('--ratio', default=0.75,
      help='Test/train split ratio.')
  parser_prep.add_argument('--hash_features', '-f', type=int,
      help='Number of hash features to generate.', default=0)

  args = parser.parse_args()

  cmds = {
      "ls": List,
      "analyze": Analyze,
      "status": Status,
      "test": Test,
      "train": Train,
      "prep": Prep,
      'roc':  ROC,
  }
  res = cmds[args.command](args)

  print json.dumps(res, indent=2)


if __name__ == '__main__':
  main()
