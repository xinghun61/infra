# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import json
import os
import re

import numpy as np
import tensorflow as tf
from googleapiclient import discovery
from googleapiclient import errors
from oauth2client.client import GoogleCredentials
from sklearn.model_selection import train_test_split
from tensorflow.contrib.learn.python.learn import learn_runner
from tensorflow.contrib.learn.python.learn.estimators import run_config
from tensorflow.contrib.learn.python.learn.utils import saved_model_export_utils
from tensorflow.contrib.training.python.training import hparam

from google.cloud.storage import blob, bucket, client

import trainer.dataset
import trainer.model
import trainer.ml_helpers
import trainer.top_words

def generate_experiment_fn(**experiment_args):
  """Create an experiment function.

  Args:
    experiment_args: keyword arguments to be passed through to experiment
      See `tf.contrib.learn.Experiment` for full args.
  Returns:
    A function:
      (tf.contrib.learn.RunConfig, tf.contrib.training.HParams) -> Experiment

    This function is used by learn_runner to create an Experiment which
    executes model code provided in the form of an Estimator and
    input functions.
  """
  def _experiment_fn(config, hparams):
    index_to_component = {}

    if hparams.train_file:
      with open(hparams.train_file) as f:
        if hparams.trainer_type == 'spam':
          training_data = trainer.ml_helpers.spam_from_file(f)
        else:
          training_data = trainer.ml_helpers.component_from_file(f)
    else:
      training_data = trainer.dataset.fetch_training_data(hparams.gcs_bucket,
        hparams.gcs_prefix, hparams.trainer_type)

    tf.logging.info('Training data received. Len: %d' % len(training_data))

    if hparams.trainer_type == 'spam':
      X, y = trainer.ml_helpers.transform_spam_csv_to_features(
          training_data)
    else:
      top_list = trainer.top_words.make_top_words_list(hparams.job_dir)
      X, y, index_to_component = trainer.ml_helpers \
          .transform_component_csv_to_features(training_data, top_list)

    tf.logging.info('Features generated')
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2,
      random_state=42)

    train_input_fn = tf.estimator.inputs.numpy_input_fn(
      x=trainer.model.feature_list_to_dict(X_train, hparams.trainer_type),
      y=np.array(y_train),
      num_epochs=hparams.num_epochs,
      batch_size=hparams.train_batch_size,
      shuffle=True
    )
    eval_input_fn = tf.estimator.inputs.numpy_input_fn(
      x=trainer.model.feature_list_to_dict(X_test, hparams.trainer_type),
      y=np.array(y_test),
      num_epochs=None,
      batch_size=hparams.eval_batch_size,
      shuffle=False # Don't shuffle evaluation data
    )

    tf.logging.info('Numpy fns created')
    if hparams.trainer_type == 'component':
      store_component_conversion(hparams.job_dir, index_to_component)

    return tf.contrib.learn.Experiment(
      trainer.model.build_estimator(config=config,
                                    trainer_type=hparams.trainer_type,
                                    class_count=len(set(y))),
      train_input_fn=train_input_fn,
      eval_input_fn=eval_input_fn,
      **experiment_args
    )
  return _experiment_fn


def store_component_conversion(job_dir, data):

  tf.logging.info('job_dir: %s' % job_dir)
  job_info = re.search('gs://(monorail-.+)-mlengine/(component_trainer_\d+)',
                       job_dir)

  # Check if training is being done on GAE or locally.
  if job_info:
    project = job_info.group(1)
    job_name = job_info.group(2)

    client_obj = client.Client(project=project)
    bucket_name = '%s-mlengine' % project
    bucket_obj = bucket.Bucket(client_obj, bucket_name)

    bucket_obj.blob = blob.Blob(job_name + '/component_index.json', bucket_obj)

    bucket_obj.blob.upload_from_string(json.dumps(data),
                                       content_type='application/json')

  else:
    paths = job_dir.split('/')
    for y, _ in enumerate(range(1, len(paths)), 1):
      if not os.path.exists("/".join(paths[:y+1])):
        os.makedirs('/'.join(paths[:y+1]))
    with open(job_dir + '/component_index.json', 'w') as f:
      f.write(json.dumps(data))


def store_eval(job_dir, results):

  tf.logging.info('job_dir: %s' % job_dir)
  job_info = re.search('gs://(monorail-.+)-mlengine/(spam_trainer_\d+)',
                       job_dir)

  # Only upload eval data if this is not being run locally.
  if job_info:
    project = job_info.group(1)
    job_name = job_info.group(2)

    tf.logging.info('project: %s' % project)
    tf.logging.info('job_name: %s' % job_name)

    client_obj = client.Client(project=project)
    bucket_name = '%s-mlengine' % project
    bucket_obj = bucket.Bucket(client_obj, bucket_name)

    bucket_obj.blob = blob.Blob(job_name + '/eval_data.json', bucket_obj)
    for key, value in results[0].iteritems():
      if isinstance(value, np.float32):
        results[0][key] = value.item()

    bucket_obj.blob.upload_from_string(json.dumps(results[0]),
                                       content_type='application/json')

  else:
    tf.logging.error('Could not find bucket "%s" to output evalution to.'
                     % job_dir)


if __name__ == '__main__':
  parser = argparse.ArgumentParser()

  # Input Arguments
  parser.add_argument(
    '--train-file',
    help='GCS or local path to training data',
  )
  parser.add_argument(
    '--gcs-bucket',
    help='GCS bucket for training data.',
  )
  parser.add_argument(
    '--gcs-prefix',
    help='Training data path prefix inside GCS bucket.',
  )
  parser.add_argument(
    '--num-epochs',
    help="""\
    Maximum number of training data epochs on which to train.
    If both --max-steps and --num-epochs are specified,
    the training job will run for --max-steps or --num-epochs,
    whichever occurs first. If unspecified will run for --max-steps.\
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
        'FATAL',
        'INFO',
        'WARN'
    ],
    default='INFO',
  )

  # Experiment arguments
  parser.add_argument(
    '--eval-delay-secs',
    help='How long to wait before running first evaluation',
    default=10,
    type=int
  )
  parser.add_argument(
    '--min-eval-frequency',
    help='Minimum number of training steps between evaluations',
    default=None,  # Use TensorFlow's default (currently, 1000)
    type=int
  )
  parser.add_argument(
    '--train-steps',
    help="""\
    Steps to run the training job for. If --num-epochs is not specified,
    this must be. Otherwise the training job will run indefinitely.\
    """,
    type=int
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

  tf.logging.set_verbosity(args.verbosity)

  # Set C++ Graph Execution level verbosity.
  os.environ['TF_CPP_MIN_LOG_LEVEL'] = str(
    tf.logging.__dict__[args.verbosity] / 10)

  # Run the training job
  # learn_runner pulls configuration information from environment
  # variables using tf.learn.RunConfig and uses this configuration
  # to conditionally execute Experiment, or param server code.
  eval_results = learn_runner.run(
    generate_experiment_fn(
      min_eval_frequency=args.min_eval_frequency,
      eval_delay_secs=args.eval_delay_secs,
      train_steps=args.train_steps,
      eval_steps=args.eval_steps,
      export_strategies=[saved_model_export_utils.make_export_strategy(
        trainer.model.SERVING_FUNCTIONS['JSON-' + args.trainer_type],
        exports_to_keep=1,
        default_output_alternative_key=None,
      )],
    ),
    run_config=run_config.RunConfig(model_dir=args.job_dir),
    hparams=hparam.HParams(**args.__dict__)
  )

  # Store a json blob in GCS with the results of training job (AUC of
  # precision/recall, etc).
  if args.trainer_type == 'spam':
    store_eval(args.job_dir, eval_results)
