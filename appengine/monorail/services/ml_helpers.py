# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""
Helper functions for spam and component classification. These are mostly for
feature extraction, so that the serving code and training code both use the same
set of features.
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import csv
import hashlib
import httplib2
import logging
import re
import sys

from apiclient.discovery import build
from apiclient.errors import Error as ApiClientError
from oauth2client.client import GoogleCredentials
from oauth2client.client import Error as Oauth2ClientError


SPAM_COLUMNS = ['verdict', 'subject', 'content', 'email']
LEGACY_CSV_COLUMNS = ['verdict', 'subject', 'content']
DELIMITERS = ['\s', '\,', '\.', '\?', '!', '\:', '\(', '\)']

# Must be identical to settings.spam_feature_hashes.
SPAM_FEATURE_HASHES = 500
# Must be identical to settings.component_features.
COMPONENT_FEATURES = 5000


def _ComponentFeatures(content, num_features, top_words):
  """
    This uses the most common words in the entire dataset as features.
    The count of common words in the issue comments makes up the features.
  """

  features = [0] * num_features
  for blob in content:
    words = blob.split()
    for word in words:
      if word in top_words:
        features[top_words[word]] += 1

  return features


def _SpamHashFeatures(content, num_features):
  """
    Feature hashing is a fast and compact way to turn a string of text into a
    vector of feature values for classification and training.
    See also: https://en.wikipedia.org/wiki/Feature_hashing
    This is a simple implementation that doesn't try to minimize collisions
    or anything else fancy.
  """
  features = [0] * num_features
  total = 0.0
  for blob in content:
    words = re.split('|'.join(DELIMITERS), blob)
    for word in words:
      feature_index = int(int(hashlib.sha1(word).hexdigest(), 16)
                          % num_features)
      features[feature_index] += 1.0
      total += 1.0

  if total > 0:
    features = [ f / total for f in features ]

  return features


def GenerateFeaturesRaw(content, num_features, top_words=None):
  """Generates a vector of features for a given issue or comment.

  Args:
    content: The content of the issue's description and comments.
    num_features: The number of features to generate.
  """
  # If we've been passed real unicode strings, convert them to just bytestrings.
  for idx, value in enumerate(content):
    if isinstance(value, unicode):
      content[idx] = value.encode('utf-8')

  if top_words:
    return { 'word_features': _ComponentFeatures(content,
                                                   num_features,
                                                   top_words)}

  return { 'word_hashes': _SpamHashFeatures(content, num_features)}


def transform_spam_csv_to_features(csv_training_data):
  X = []
  y = []
  for row in csv_training_data:
    verdict, subject, content = row
    X.append(GenerateFeaturesRaw([str(subject), str(content)],
                                 SPAM_FEATURE_HASHES))
    y.append(1 if verdict == 'spam' else 0)
  return X, y


def transform_component_csv_to_features(csv_training_data, top_list):
  X = []
  y = []
  top_words = {}

  for i in range(len(top_list)):
    top_words[top_list[i]] = i

  component_to_index = {}
  index_to_component = {}
  component_index = 0

  for row in csv_training_data:
    component, content = row
    component = str(component).split(",")[0]

    if component not in component_to_index:
      component_to_index[component] = component_index
      index_to_component[component_index] = component
      component_index += 1

    X.append(GenerateFeaturesRaw([content],
                                 COMPONENT_FEATURES,
                                 top_words))
    y.append(component_to_index[component])

  return X, y, index_to_component


def spam_from_file(f):
  """Reads a training data file and returns an array."""
  rows = []
  skipped_rows = 0
  for row in csv.reader(f):
    if len(row) == len(SPAM_COLUMNS):
      # Throw out email field.
      rows.append(row[:3])
    elif len(row) == len(LEGACY_CSV_COLUMNS):
      rows.append(row)
    else:
      skipped_rows += 1
  return rows, skipped_rows


def component_from_file(f):
  """Reads a training data file and returns an array."""
  rows = []
  csv.field_size_limit(sys.maxsize)
  for row in csv.reader(f):
    rows.append(row)

  return rows


def setup_ml_engine():
  """Sets up an instance of ml engine for ml classes."""
  try:
    credentials = GoogleCredentials.get_application_default()
    ml_engine = build('ml', 'v1', http=httplib2.Http(), credentials=credentials)
    return ml_engine

  except (Oauth2ClientError, ApiClientError):
    logging.error("Error setting up ML Engine API: %s" % sys.exc_info()[0])
