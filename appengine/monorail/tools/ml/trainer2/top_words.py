# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# Or at https://developers.google.com/open-source/licenses/bsd

from __future__ import absolute_import

import os

import train_ml_helpers


def GenerateTopWords(word_dict):
  """Requires ./stopwords.txt exist in folder for the function to run.
  """
  with open('./stopwords.txt', 'r') as f:
    stop_words = f.read().encode('utf-8').split()
  sorted_words = sorted(word_dict, key=word_dict.get, reverse=True)

  top_words = []
  index = 0

  while len(top_words) < train_ml_helpers.COMPONENT_FEATURES:
    if sorted_words[index] not in stop_words:
      top_words.append(sorted_words[index])
    index += 1

  return top_words


def parse_words_from_content(contents):
  """Returns given list of strings, extract the top (most common) words.
  """
  word_dict = {}
  for content in contents:
    words = content.encode('utf-8').split()
    for word in words:
      if word in word_dict:
        word_dict[word] += 1
      else:
        word_dict[word] = 1

  return GenerateTopWords(word_dict)


def make_top_words_list(contents, job_dir):
  """Returns the top (most common) words in the entire dataset for component
  prediction. If a file is already stored in job_dir containing these words, the
  words from the file are simply returned. Otherwise, the most common words are
  determined and written to job_dir, before being returned.

  Returns:
    A list of the most common words in the dataset (the number of them
    determined by train_ml_helpers.COMPONENT_FEATURES).
  """
  if not os.path.exists(job_dir):
    os.mkdir(job_dir)
  if os.access(job_dir + 'topwords.txt', os.R_OK):
    print("Found topwords.txt")
    with open(job_dir + 'topwords.txt', 'rb') as f:
      top_words = f.read().split()
  else:
    top_words = parse_words_from_content(contents)
    with open(job_dir + 'topwords.txt', 'w') as f:
      for word in top_words:
        f.write('%s\n' % word.decode('utf-8'))
  return top_words
