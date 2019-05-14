# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import tensorflow as tf

from trainer.ml_helpers import COMPONENT_FEATURES
from trainer.ml_helpers import SPAM_FEATURE_HASHES

# Important: we assume this list mirrors the output of GenerateFeaturesRaw.
INPUT_COLUMNS = {'component': [
                     tf.feature_column.numeric_column(
                         key='word_features',
                         shape=(COMPONENT_FEATURES,)),
                 ],
                 'spam': [
                     tf.feature_column.numeric_column(
                         key='word_hashes',
                         shape=(SPAM_FEATURE_HASHES,)),
                 ]}


def build_estimator(config, trainer_type, class_count):
  """Returns a tf.Estimator.

  Args:
    config: tf.contrib.learn.RunConfig defining the runtime environment for the
      estimator (including model_dir).
  Returns:
    A LinearClassifier
  """
  return tf.contrib.learn.DNNClassifier(
    config=config,
    feature_columns=(INPUT_COLUMNS[trainer_type]),
    hidden_units=[1024, 512, 256],
    optimizer=tf.train.AdamOptimizer(learning_rate=0.001,
      beta1=0.9,
      beta2=0.999,
      epsilon=1e-08,
      use_locking=False,
      name='Adam'),
    n_classes=class_count
  )


def feature_list_to_dict(X, trainer_type):
  """Converts an array of feature dicts into to one dict of
    {feature_name: [feature_values]}.

  Important: this assumes the ordering of X and INPUT_COLUMNS is the same.

  Args:
    X: an array of feature dicts
  Returns:
    A dictionary where each key is a feature name its value is a numpy array of
    shape (len(X),).
  """
  feature_dict = {}

  for feature_column in INPUT_COLUMNS[trainer_type]:
    feature_dict[feature_column.name] = []

  for instance in X:
    for key in instance.keys():
      feature_dict[key].append(instance[key])

  for key in [f.name for f in INPUT_COLUMNS[trainer_type]]:
    feature_dict[key] = np.array(feature_dict[key])

  return feature_dict


def generate_json_serving_input_fn(trainer_type):
  def json_serving_input_fn():
    """Build the serving inputs.

    Returns:
      An InputFnOps containing features with placeholders.
    """
    features_placeholders = {}
    for column in INPUT_COLUMNS[trainer_type]:
      name = '%s_placeholder' % column.name

      # Special case non-scalar features.
      if column.shape[0] > 1:
        shape = [None, column.shape[0]]
      else:
        shape = [None]

      placeholder = tf.placeholder(tf.float32, shape, name=name)
      features_placeholders[column.name] = placeholder

    labels = None # Unknown at serving time
    return tf.contrib.learn.InputFnOps(features_placeholders, labels,
      features_placeholders)

  return json_serving_input_fn


SERVING_FUNCTIONS = {
    'JSON-component': generate_json_serving_input_fn('component'),
    'JSON-spam':  generate_json_serving_input_fn('spam')
}
