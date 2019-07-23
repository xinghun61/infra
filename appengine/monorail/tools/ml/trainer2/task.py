# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# Or at https://developers.google.com/open-source/licenses/bsd

from __future__ import absolute_import

import argparse
import json
import os

import tensorflow as tf
from tensorflow.estimator import RunConfig
from sklearn.model_selection import train_test_split

import model
import top_words
import logging
import train_ml_helpers
from train_ml_helpers import COMPONENT_FEATURES
from train_ml_helpers import SPAM_FEATURE_HASHES

INPUT_TYPE_MAP = {
  'component': {'key': 'word_features', 'shape': (COMPONENT_FEATURES,)},
  'spam': {'key': 'word_hashes', 'shape': (SPAM_FEATURE_HASHES,)}
}


def make_input_fn(trainer_type, features, targets,
  num_epochs=None, shuffle=True, batch_size=128):
  """Generate input function for training and testing.

  Args:
    trainer_type: spam / component
    features: an array of features shape like INPUT_TYPE_MAP
    targets: an array of labels with the same length of features
    num_epochs: training epochs
    batch_size: dataset batch size

  Returns:
    input function to feed into TrainSpec and EvalSpec.
  """
  def _input_fn():
    def gen():
      """Generator function to format feature and target. """
      for feature, target in zip(features, targets):
        yield feature[INPUT_TYPE_MAP[trainer_type]['key']], target

    dataset = tf.data.Dataset.from_generator(gen, (tf.float64, tf.int32),
      output_shapes=(INPUT_TYPE_MAP[trainer_type]['shape'], ()))
    dataset = dataset.map(lambda x, y:
      ({INPUT_TYPE_MAP[trainer_type]['key']: x}, y))
    if shuffle:
      dataset = dataset.shuffle(buffer_size=batch_size * 10)
    dataset = dataset.repeat(num_epochs).batch(batch_size)
    return dataset
  return _input_fn


def generate_json_input_fn(trainer_type):
  """Generate ServingInputReceiver function for testing.

  Args:
    trainer_type: spam / component

  Returns:
    ServingInputReceiver function to feed into exporter.
  """
  feature_spec = {
    INPUT_TYPE_MAP[trainer_type]['key']:
    tf.io.FixedLenFeature(INPUT_TYPE_MAP[trainer_type]['shape'], tf.float32)
  }
  return tf.estimator.export.build_parsing_serving_input_receiver_fn(
    feature_spec)


def train_and_evaluate_model(config, hparams):
  """Runs the local training job given provided command line arguments.

  Args:
    config: RunConfig object
    hparams: dictionary passed by command line arguments

  """

  with open(hparams['train_file']) as f:
    if hparams['trainer_type'] == 'spam':
      contents, labels, _ = train_ml_helpers.spam_from_file(f)
    else:
      contents, labels = train_ml_helpers.component_from_file(f)

  logger.info('Training data received. Len: %d' % len(contents))

  # Generate features and targets from extracted contents and labels.
  if hparams['trainer_type'] == 'spam':
    features, targets = train_ml_helpers \
      .transform_spam_csv_to_features(contents, labels)
  else:
    top_list = top_words.make_top_words_list(contents, hparams['job_dir'])
    features, targets, index_to_component = train_ml_helpers \
      .transform_component_csv_to_features(contents, labels, top_list)

  # Split training and testing set.
  logger.info('Features generated')
  features_train, features_test, targets_train, targets_test = train_test_split(
      features, targets, test_size=0.2, random_state=42)

  # Generate TrainSpec and EvalSpec for train and evaluate.
  estimator = model.build_estimator(config=config,
                                    job_dir=hparams['job_dir'],
                                    trainer_type=hparams['trainer_type'],
                                    class_count=len(set(labels)))
  exporter = tf.estimator.LatestExporter(name='saved_model',
    serving_input_receiver_fn=generate_json_input_fn(hparams['trainer_type']))

  train_spec = tf.estimator.TrainSpec(
    input_fn=make_input_fn(hparams['trainer_type'],
    features_train, targets_train, num_epochs=hparams['num_epochs'],
    batch_size=hparams['train_batch_size']),
    max_steps=hparams['train_steps'])
  eval_spec = tf.estimator.EvalSpec(
    input_fn=make_input_fn(hparams['trainer_type'],
    features_test, targets_test, shuffle=False,
    batch_size=hparams['eval_batch_size']),
    exporters=exporter, steps=hparams['eval_steps'])

  if hparams['trainer_type'] == 'component':
      store_component_conversion(hparams['job_dir'], index_to_component)

  result = tf.estimator.train_and_evaluate(estimator, train_spec, eval_spec)
  logging.info(result)


def store_component_conversion(job_dir, data):
  logger.info('job_dir: %s' % job_dir)

  # Store component conversion locally.
  paths = job_dir.split('/')
  for y, _ in enumerate(list(range(1, len(paths))), 1):
    if not os.path.exists("/".join(paths[:y+1])):
      os.makedirs('/'.join(paths[:y+1]))
  with open(job_dir + '/component_index.json', 'w') as f:
    f.write(json.dumps(data))


if __name__ == '__main__':
  parser = argparse.ArgumentParser()

  # Input Arguments
  parser.add_argument(
    '--train-file',
    help='GCS or local path to training data',
    required=True
  )
  parser.add_argument(
    '--num-epochs',
    help="""\
    Maximum number of training data epochs on which to train.
    If both --train-steps and --num-epochs are specified,
    the training job will run for --num-epochs.
    If unspecified will run for --train-steps.\
    """,
    type=int,
  )
  parser.add_argument(
    '--train-batch-size',
    help='Batch size for training steps',
    type=int,
    default=128
  )
  parser.add_argument(
    '--eval-batch-size',
    help='Batch size for evaluation steps',
    type=int,
    default=128
  )

  # Training arguments
  parser.add_argument(
    '--job-dir',
    help='GCS location to write checkpoints and export models',
    required=True
  )

  # Logging arguments
  parser.add_argument(
    '--verbosity',
    choices=[
        'DEBUG',
        'ERROR',
        'CRITICAL',
        'INFO',
        'WARNING'
    ],
    default='INFO',
  )

  # Input function arguments
  parser.add_argument(
    '--train-steps',
    help="""\
    Steps to run the training job for. If --num-epochs is not specified,
    this must be. Otherwise the training job will run indefinitely.\
    """,
    type=int,
    required=True
  )
  parser.add_argument(
    '--eval-steps',
    help='Number of steps to run evalution for at each checkpoint',
    default=100,
    type=int
  )
  parser.add_argument(
    '--trainer-type',
    help='Which trainer to use (spam or component)',
    choices=['spam', 'component'],
    required=True
  )

  args = parser.parse_args()

  logger = logging.getLogger()
  logger.setLevel(getattr(logging, args.verbosity))

  if not args.num_epochs:
    args.num_epochs = args.train_steps

  # Set C++ Graph Execution level verbosity.
  os.environ['TF_CPP_MIN_LOG_LEVEL'] = str(
    getattr(logging, args.verbosity) / 10)

  # Run the training job.
  train_and_evaluate_model(
    config=RunConfig(model_dir=args.job_dir),
    hparams=vars(args))
