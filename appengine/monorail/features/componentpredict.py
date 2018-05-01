# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import json
import logging
import re
import settings

import cloudstorage
from googleapiclient import discovery
from googleapiclient import errors
from oauth2client.client import GoogleCredentials

from features import generate_dataset
from framework import sql
from framework import jsonfeed
from framework import framework_helpers
from services import ml_helpers
from tracker import tracker_bizobj


class ComponentPredict(jsonfeed.JsonFeed):
  """Serves suggestions for components by getting a prediction from the default
  component model given the provided text.
  """

  top_words = {}

  def InitializeTopWords(self, trainer_name):
    """Gets list of top words from GCS to be used as features for component
    prediction.
    """

    credentials = GoogleCredentials.get_application_default()
    storage = discovery.build('storage', 'v1', credentials=credentials)
    objects = storage.objects()

    request = objects.get_media(bucket=settings.component_ml_bucket,
                                object=trainer_name + '/topwords.txt')
    response = request.execute()
    top_list = response.split()

    # This turns the top words list into a dictionary for faster feature
    # generation.
    for i in range(len(top_list)):
      self.top_words[top_list[i]] = i

    logging.info('Length of top words list: %s', len(self.top_words))


  def Predict(self, instance, ml_engine, model_name, trainer_name):
    """High-level method that takes an input and returns the model's prediction.

    Args:
      instance (list): A single sample on which to make a prediction
        (output from GenerateFeaturesRaw).
      ml_engine: An ML Engine API instance.
      model_name (str): The hosted model to call.
      trainer_name (str): The name of the trainer that generated this
        model. Used to fetch component ID to index mapping.

    Returns:
      A dict: {'components': []}. The list will either be empty or contain
      one ComponentDef representing the top predicted component.
    """
    components = []
    best_score_index = self.GetPrediction(instance, ml_engine, model_name)
    component_id = self.GetComponentID(trainer_name, best_score_index)
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)
    component = tracker_bizobj.FindComponentDefByID(component_id, config)
    if component:
      components.append(component)

    return {'components': components}


  @framework_helpers.retry(3)
  def GetPrediction(self, instance, ml_engine, model_name):
    """Gets component prediction from default model based on provided text.

    Args:
      instance: The dict object returned from ml_helpers.GenerateFeaturesRaw
        containing the features generated from the provided text.
      ml_engine: An ML Engine instance for making predictions.
      model_name: The full path to the model's location.

    Returns:
      The index of the component with the highest score. ML engine's predict
      api returns a dict of the format
      {'predictions': [{'classes': ['0', '1', ...], 'scores': [.00234, ...]}]}
      where each class has a score at the same index. Classes are sequential,
      so the index of the highest score also happens to be the component's
      index.
    """
    body = {'instances': [{'inputs': instance['word_features']}]}

    request = ml_engine.projects().predict(name=model_name, body=body)
    response = request.execute()

    logging.info('ML Engine API response: %r' % response)

    prediction_dict = response['predictions'][0]
    scores = prediction_dict['scores']

    return scores.index(max(scores))


  def GetComponentID(self, trainer_name, index):
    """Gets the actual component ID from the provided index by getting the
    mapping of indexes to IDs, which is stored in the bucket where the model's
    trainer is stored.

    Args:
      trainer_name: The name of the trainer that generated the current default
        model.
      index: The index of the component we want to get the ID of.

    Returns:
      The component ID of the provided component, determined by the index/ID
      mapping.
    """

    mapping_path = '/%s/%s/component_index.json' % (
        settings.component_ml_bucket, trainer_name)

    logging.info('Mapping path full name: %r', mapping_path)

    # TODO(carapew): Memcache the index mapping file.
    gcs_file = cloudstorage.open(mapping_path, mode='r')

    logging.info('Index component mapping opened')

    component_index = json.load(gcs_file)

    component_id = component_index[str(index)]

    gcs_file.close()

    return component_id


  def HandleRequest(self, mr):

    text = mr.request.POST.items()[0][1]
    logging.info('text: %r', text)
    clean_text = generate_dataset.CleanText(text)

    ml_engine = ml_helpers.setup_ml_engine()

    model_name = 'projects/%s/models/%s' % (
      settings.classifier_project_id, settings.component_model_name)

    model_request = ml_engine.projects().models().get(name=model_name)

    model_response = model_request.execute()

    version_name = model_response['defaultVersion']['name']

    # Gets the timestamp number from the folder containing the model's trainer
    # in order to get the correct files for mappings and features.
    trainer_name = 'component_trainer_' + re.search('v_(\d+)',
                                                    version_name).group(1)

    # TODO(carapew): Use memcache to get top words rather than storing as a
    # variable of ComponentPredict.
    if self.top_words == {}:
      self.InitializeTopWords(trainer_name)

    instance = ml_helpers.GenerateFeaturesRaw(
        [clean_text],
        settings.component_features,
        self.top_words
    )

    prediction = self.Predict(instance, ml_engine, model_name, trainer_name)
    logging.info('prediction: %r', str(prediction))
    return prediction

