# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# Or at https://developers.google.com/open-source/licenses/bsd

"""
Helper functions for spam and component classification. These are mostly for
feature extraction, so that the serving code and training code both use the same
set of features.
TODO(jeffcarp): This file is duplicate of services/ml_helpers.py
  (with slight difference). Will eventually be merged to one.
"""

from __future__ import absolute_import

import csv
import hashlib
import re
import sys

SPAM_COLUMNS = ['verdict', 'subject', 'content', 'email']
LEGACY_CSV_COLUMNS = ['verdict', 'subject', 'content']
DELIMITERS = [r'\s', r'\,', r'\.', r'\?', r'!', r'\:', r'\(', r'\)']

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
    words = re.split('|'.join(DELIMITERS).encode('utf-8'), blob)
    for word in words:
      feature_index = int(int(hashlib.sha1(word).hexdigest(), 16)
                          % num_features)
      features[feature_index] += 1.0
      total += 1.0

  if total > 0:
    features = [f / total for f in features]

  return features


def GenerateFeaturesRaw(content, num_features, top_words=None):
  """Generates a vector of features for a given issue or comment.

  Args:
    content: The content of the issue's description and comments.
    num_features: The number of features to generate.
  """
  # If we've been passed real unicode strings, convert them to just bytestrings.
  for idx, value in enumerate(content):
    content[idx] = value.encode('utf-8')
  if top_words:
    return {'word_features': _ComponentFeatures(content,
                                                   num_features,
                                                   top_words)}

  return {'word_hashes': _SpamHashFeatures(content, num_features)}


def transform_spam_csv_to_features(contents, labels):
  """Generate arrays of features and targets for spam.
  """
  features = []
  targets = []
  for i, row in enumerate(contents):
    subject, content = row
    label = labels[i]
    features.append(GenerateFeaturesRaw([str(subject), str(content)],
                                 SPAM_FEATURE_HASHES))
    targets.append(1 if label == 'spam' else 0)
  return features, targets


def transform_component_csv_to_features(contents, labels, top_list):
  """Generate arrays of features and targets for components.
  """
  features = []
  targets = []
  top_words = {}

  for i, row in enumerate(top_list):
    top_words[row] = i

  component_to_index = {}
  index_to_component = {}
  component_index = 0

  for i, content in enumerate(contents):
    component = labels[i]
    component = str(component).split(",")[0]

    if component not in component_to_index:
      component_to_index[component] = component_index
      index_to_component[component_index] = component
      component_index += 1

    features.append(GenerateFeaturesRaw([content],
                                 COMPONENT_FEATURES,
                                 top_words))
    targets.append(component_to_index[component])

  return features, targets, index_to_component


def spam_from_file(f):
  """Reads a training data file and returns arrays of contents and labels."""
  contents = []
  labels = []
  skipped_rows = 0
  for row in csv.reader(f):
    if len(row) >= len(LEGACY_CSV_COLUMNS):
      # Throw out email field.
      contents.append(row[1:3])
      labels.append(row[0])
    else:
      skipped_rows += 1
  return contents, labels, skipped_rows


def component_from_file(f):
  """Reads a training data file and returns arrays of contents and labels."""
  contents = []
  labels = []
  csv.field_size_limit(sys.maxsize)
  for row in csv.reader(f):
    label, content = row
    contents.append(content)
    labels.append(label)
  return contents, labels
