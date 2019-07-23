# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# Or at https://developers.google.com/open-source/licenses/bsd

from __future__ import absolute_import

import tensorflow as tf

from train_ml_helpers import COMPONENT_FEATURES
from train_ml_helpers import SPAM_FEATURE_HASHES

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

def build_estimator(config, job_dir, trainer_type, class_count):
  """Returns a tf.Estimator.

  Args:
    config: tf.contrib.learn.RunConfig defining the runtime environment for the
      estimator (including model_dir).
  Returns:
    A LinearClassifier
  """
  return tf.estimator.DNNClassifier(
    config=config,
    model_dir=job_dir,
    feature_columns=(INPUT_COLUMNS[trainer_type]),
    hidden_units=[1024, 512, 256],
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001,
      beta_1=0.9,
      beta_2=0.999,
      epsilon=1e-08,
      name='Adam'),
    n_classes=class_count
  )
