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
import zlib

_LINKIFY_SCHEMES = r'(https?://|ftp://|mailto:)'
_IS_A_LINK_RE = re.compile(r'(%s)([^\s<]+)' % _LINKIFY_SCHEMES, re.UNICODE)


def _ExtractUrls(text):
  matches = _IS_A_LINK_RE.findall(text)
  if not matches:
    return []

  ret = [''.join(match[1:]).replace('\\r', '') for match in matches]
  return ret


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

  # Compression ratio lets us know how much repeated data there is.
  uncompressed_summary_len = len(summary)
  uncompressed_description_len = len(description)
  compressed_summary_len = len(zlib.compress(summary))
  compressed_description_len = len(zlib.compress(description))

  # If hash features are requested, generate those instead of
  # the raw text.
  feature_hashes = _HashFeatures([summary, description], num_hashes)

  urls = _ExtractUrls(description)
  num_urls_feature = len(urls) if urls else 0
  num_duplicate_urls_feature = len(urls) - len(list(set(urls)))

  return {
    'num_urls': num_urls_feature,
    'num_duplicate_urls': num_duplicate_urls_feature,
    'uncompressed_summary_len': uncompressed_summary_len,
    'compressed_summary_len': compressed_summary_len,
    'uncompressed_description_len': uncompressed_description_len,
    'compressed_description_len': compressed_description_len,
    'word_hashes': feature_hashes,
  }


def GenerateFeatures(summary, description, num_hashes):
  """Stringifies GenerateFeatures.

  This function must be named GenerateFeatures to preserve
  backward-compatibility.
  """

  features = GenerateFeaturesRaw(summary, description, num_hashes)
  return [
    '%s' % features['num_urls'],
    '%s' % features['num_duplicate_urls'],
    '%s' % features['uncompressed_summary_len'],
    '%s' % features['compressed_summary_len'],
    '%s' % features['uncompressed_description_len'],
    '%s' % features['compressed_description_len'],
   ] + ['%f' % f for f in features['word_hashes']]
