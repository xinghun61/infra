# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.join(
  os.path.dirname(os.path.dirname(__file__)), 'third_party'))

import cloudstorage


BUCKET = 'flake-predictor-data/log_data'


def get_json_file(file_path):
  """Retrieve the json file in GS.

  Function to retrieve the test data, which is stored in
  GS. If the file cannot be opened, returns None.
  """
  try:
    gcs_file = cloudstorage.open(file_path)
  except cloudstorage.NotFoundError:
    logging.error('Error: file on path %s not found ' % file_path)
    return None

  json_string = gcs_file.read()
  gcs_file.close()

  try:
    json_file = json.loads(json_string)
  except ValueError:
    logging.error('Error: could not parse json file %s' % file_path)
    return None

  return json_file

def get_raw_output_snippet(json_file, test_name):
  """Retrieve the output snippet from a json file.

  Function to retrieve the output snippet from a json file.
  If the test data is not in the flake-predictor bucket, the
  returned file does not have the correct fields, or the test
  data is not in the file, return None. Otherwise, return the snippet.
  """
  if json_file == None:
    return None
  if test_name not in json_file.get('all_tests', {}):
    return None

  test_data = json_file["per_iteration_data"][0][test_name]
  snippet = test_data[0]['output_snippet']
  return snippet

def process_snippet(snippet):
  """Process and clean output snippet.

  Function for taking a snippet as a large string and processing it into
  a list of separate words. Punctuation and other extaneous symbols are
  also removed.
  """
  # Remove the pointers/noisy numbers
  snippet = re.sub(r"\[\d+\:\d+\:\d+\/\d+\.\d+",'', snippet)
  # Remove periods at the end of sentences
  snippet = re.sub(r"\.(\s)", ' ', snippet)
  # Remove some punctuation entirely
  snippet = snippet.replace('[', '').replace(']', '').replace('"', '')
  snippet = snippet.replace('(', '').replace(')', '')
  # Replace some punctuation with spaces so that it will be split on
  snippet = snippet.replace(':', ' ').replace('=', ' ')

  return (snippet.split())

def get_processed_output_snippet_batch(
    master_name, builder_name, build_number, step_name, tests):
  """Retrieve output snippet for many tests in a given step.

  Function that takes a step and list of tests and returns the
  output snippets, as a dictonary, for that each test properly formatted.
  """
  file_path = "/%s/%s/%s/%s/%s.json" % (BUCKET, master_name, builder_name,
                                        build_number, step_name)
  json_file = get_json_file(file_path)

  cleaned_snippets = {}
  for test_name in tests:
    snippet = get_raw_output_snippet(json_file, test_name)
    if snippet != None:
      snippet = process_snippet(snippet)
      cleaned_snippets[test_name] = snippet
  return cleaned_snippets
