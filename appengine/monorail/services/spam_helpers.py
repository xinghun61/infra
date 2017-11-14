# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""
Spam classifier helper functions. These are mostly fo feature extraction, so
that the serving code and training code both use the same set of features.
"""

import hashlib
import re


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
  total = 0.0
  for blob in content:
    words = re.split('|'.join(DELIMITERS), blob)
    for w in words:
      feature_index = int(int(hashlib.sha1(w).hexdigest(), 16) % num_features)
      features[feature_index] += 1.0
      total += 1.0

  if total > 0:
    features = [ f / total for f in features ]

  return features


def GenerateFeaturesRaw(summary, description, num_hashes):
  """Generates a vector of features for a given issue or comment.

  Args:
    summary: The summary text of the Issue.
    description: The description of the Issue or the content of the Comment.
    num_hashes: The number of feature hashes to generate.
  """
  # If we've been passed real unicode strings, convert them to just bytestrings.
  if isinstance(summary, unicode):
    summary = summary.encode('utf-8')
  if isinstance(description, unicode):
    description = description.encode('utf-8')

  return { 'word_hashes': _HashFeatures([summary, description], num_hashes) }
