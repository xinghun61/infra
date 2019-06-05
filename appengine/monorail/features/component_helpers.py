# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import logging
import re

import settings
import cloudstorage

from features import generate_dataset
from framework import framework_helpers
from services import ml_helpers
from tracker import tracker_bizobj

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials


MODEL_NAME = 'projects/{}/models/{}'.format(
    settings.classifier_project_id, settings.component_model_name)


def _GetTopWords(trainer_name):  # pragma: no cover
  # TODO(carapew): Use memcache to get top words rather than storing as a
  # variable.
  credentials = GoogleCredentials.get_application_default()
  storage = discovery.build('storage', 'v1', credentials=credentials)
  request = storage.objects().get_media(
      bucket=settings.component_ml_bucket,
      object=trainer_name + '/topwords.txt')
  response = request.execute()

  # This turns the top words list into a dictionary for faster feature
  # generation.
  return {word: idx for idx, word in enumerate(response.split())}


def _GetComponentsByIndex(trainer_name):
  # TODO(carapew): Memcache the index mapping file.
  mapping_path = '/%s/%s/component_index.json' % (
      settings.component_ml_bucket, trainer_name)
  logging.info('Mapping path full name: %r', mapping_path)

  with cloudstorage.open(mapping_path, 'r') as index_mapping_file:
    logging.info('Index component mapping opened')
    mapping = index_mapping_file.read()
    logging.info(mapping)
    return json.loads(mapping)


@framework_helpers.retry(3)
def _GetComponentPrediction(ml_engine, instance):
  """Predict the component from the default model based on the provided text.

  Args:
    ml_engine: An ML Engine instance for making predictions.
    instance: The dict object returned from ml_helpers.GenerateFeaturesRaw
      containing the features generated from the provided text.

  Returns:
    The index of the component with the highest score. ML engine's predict
    api returns a dict of the format
    {'predictions': [{'classes': ['0', '1', ...], 'scores': [.00234, ...]}]}
    where each class has a score at the same index. Classes are sequential,
    so the index of the highest score also happens to be the component's
    index.
  """
  body = {'instances': [{'inputs': instance['word_features']}]}
  request = ml_engine.projects().predict(name=MODEL_NAME, body=body)
  response = request.execute()

  logging.info('ML Engine API response: %r' % response)
  scores = response['predictions'][0]['scores']

  return scores.index(max(scores))


def PredictComponent(raw_text, config):
  """Get the component ID predicted for the given text.

  Args:
    raw_text: The raw text for which we want to predict a component.
    config: The config of the project. Used to decide if the predicted component
        is valid.

  Returns:
    The component ID predicted for the provided component, or None if no
    component was predicted.
  """
  # Set-up ML engine.
  ml_engine = ml_helpers.setup_ml_engine()

  # Gets the timestamp number from the folder containing the model's trainer
  # in order to get the correct files for mappings and features.
  request = ml_engine.projects().models().get(name=MODEL_NAME)
  response = request.execute()

  version = re.search(r'v_(\d+)', response['defaultVersion']['name']).group(1)
  trainer_name = 'component_trainer_%s' % version

  top_words = _GetTopWords(trainer_name)
  components_by_index = _GetComponentsByIndex(trainer_name)
  logging.info('Length of top words list: %s', len(top_words))

  clean_text = generate_dataset.CleanText(raw_text)
  instance = ml_helpers.GenerateFeaturesRaw(
      [clean_text], settings.component_features, top_words)

  # Get the component id with the highest prediction score. Component ids are
  # stored in GCS as strings, but represented in the app as longs.
  best_score_index = _GetComponentPrediction(ml_engine, instance)
  component_id = components_by_index.get(str(best_score_index))
  if component_id:
    component_id = long(component_id)

  # The predicted component id might not exist.
  if tracker_bizobj.FindComponentDefByID(component_id, config) is None:
    return None

  return component_id
