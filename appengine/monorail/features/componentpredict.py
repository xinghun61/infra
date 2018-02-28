# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import json
import logging
import re
import settings

import cloudstorage

from framework import sql
from services import ml_helpers
from framework import jsonfeed

from features import generate_dataset


class ComponentPredict(jsonfeed.JsonFeed):
  """Serves suggestions for components by getting a prediction from the default
  component model given the provided text.
  """

  def Predict(self, instance):
    ml_engine = ml_helpers.setup_ml_engine()

    model_name = 'projects/%s/models/%s' % (
      settings.classifier_project_id, settings.component_model_name)

    best_score_index = self.GetPrediction(instance, ml_engine, model_name)

    component_id = self.GetComponentID(ml_engine, model_name, best_score_index)

    return {'components': [self.GetComponent(component_id)]}


  def GetPrediction(self, instance, ml_engine, model_name):
    """Gets component prediction from default model based on provided text.

    Returns:
      The index of the component with the highest score. ML engine's predict
      api returns a dict of the format
      {'predictions': [{'classes': ['0', '1', ...], 'scores': [.00234, ...]}]}
      where each class has a score at the same index. Classes are sequential,
      so the index of the highest score also happens to be the component's
      index.
    """
    body = {'instances': [{'inputs': instance['word_hashes']}]}

    request = ml_engine.projects().predict(name=model_name, body=body)
    response = request.execute()

    logging.info('ML Engine API response: %r' % response)

    prediction_dict = response['predictions'][0]
    scores = prediction_dict['scores']

    return scores.index(max(scores))


  def GetComponentID(self, ml_engine, model_name, index):
    """Gets the actual component ID from the provided index by getting the
    mapping of indexes to IDs, which is stored in the bucket where the model's
    trainer is stored.

    Args:
      model_name: The name of the model to get the default version of.
      index: The index of the component we want to get the ID of.

    Returns:
      The component ID of the provided component, determined by the index/ID
      mapping.
    """

    bucket_name = settings.component_ml_bucket

    model_request = ml_engine.projects().models().get(name=model_name)
    model_response = model_request.execute()
    version_name = model_response['defaultVersion']['name']

    # Gets the timestamp number from the folder containing the model's trainer
    # in order to get the correct index/component mapping.
    model_full_name = 'component_trainer_' + re.search('v_(\d+)',
                                                       version_name).group(1)

    model_path = '/%s/%s/component_index.json' % (bucket_name,
                                                    model_full_name)

    logging.info('Model full name: %r', model_path)

    #TODO(carapew): Memcache the index mapping file.
    gcs_file = cloudstorage.open(model_path, mode='r')

    logging.info('Index component mapping opened')

    component_index = json.load(gcs_file)

    component_id = component_index[str(index)]

    gcs_file.close()

    return component_id


  def GetComponent(self, component_id):

    con = sql.MonorailConnection()

    component_table = sql.SQLTableManager('ComponentDef')

    component_name = component_table.SelectValue(
        con,
        col='path',
        where=[('id = %s', [str(component_id)])])

    return component_name


  def HandleRequest(self, mr):

    text = mr.request.POST.items()[0][1]
    logging.info('text: %r', text)
    clean_text = generate_dataset.CleanText(text)

    instance = ml_helpers.GenerateFeaturesRaw(
        [clean_text],
        settings.component_feature_hashes)

    prediction = self.Predict(instance)
    logging.info('prediction: %r', str(prediction))
    return prediction

