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

SKETCHY_EMAIL_RE = re.compile('[a-za-z]+[0-9]+\@.+')

def _EmailIsSketchy(email, whitelisted_suffixes):
  if email.endswith(whitelisted_suffixes):
    return False
  return SKETCHY_EMAIL_RE.match(email) is not None

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

def GenerateFeatures(summary, description, author_email, num_hashes,
      whitelisted_email_suffixes):
  """ Generates a vector of features for a given issue or comment.

  Args:
    summary: The summary text of the Issue.
    description: The description of the Issue or the content of the Comment.
    author_email: The email address of the Issue or Comment author.
    num_hashes: The number of feature hashes to generate.
    whitelisted_email_suffixes: The set of email address suffixes to ignore.
  """
  summary = summary.encode('utf-8')
  description = description.encode('utf-8')

  # Compression ratio lets us know how much repeated data there is.
  uncompressed_summary_len = len(summary)
  uncompressed_description_len = len(description)
  compressed_summary_len = len(zlib.compress(summary))
  compressed_description_len = len(zlib.compress(description))

  # If hash features are requested, generate those instead of
  # the raw text.
  feature_hashes = _HashFeatures([summary, description], num_hashes)

  # author email is in the 4th column.
  sketchy_email_feature = _EmailIsSketchy(author_email,
      whitelisted_email_suffixes)
  urls = _ExtractUrls(description)
  num_urls_feature = len(urls) if urls else 0
  num_duplicate_urls_feature = len(urls) - len(list(set(urls)))

  ret = [
    '%s' % sketchy_email_feature,
    '%s' % num_urls_feature,
    '%s' % num_duplicate_urls_feature,
    '%s' % uncompressed_summary_len,
    '%s' % compressed_summary_len,
    '%s' % uncompressed_description_len,
    '%s' % compressed_description_len,
   ]

  ret.extend(['%d' % f for f in feature_hashes])
  return ret

