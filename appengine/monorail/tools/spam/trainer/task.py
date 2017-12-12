# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import argparse
import os

import numpy as np
import tensorflow as tf
from sklearn.model_selection import train_test_split
from tensorflow.contrib.learn.python.learn import learn_runner
from tensorflow.contrib.learn.python.learn.estimators import run_config
from tensorflow.contrib.learn.python.learn.utils import saved_model_export_utils
from tensorflow.contrib.training.python.training import hparam

import trainer.dataset
import trainer.model


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
    if hparams.train_file:

      with open(hparams.train_file) as f:
        training_data, _ = trainer.dataset.from_file(f)
    else:
      training_data = trainer.dataset.fetch_training_data(hparams.gcs_bucket,
        hparams.gcs_prefix)

    tf.logging.info('Training data received. Len: %d' % len(training_data))

    X, y = trainer.dataset.transform_csv_to_features(training_data)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2,
      random_state=42)

    train_input_fn = tf.estimator.inputs.numpy_input_fn(
      x=trainer.model.feature_list_to_dict(X_train),
      y=np.array(y_train),
      num_epochs=hparams.num_epochs,
      batch_size=hparams.train_batch_size,
      shuffle=True
    )
    eval_input_fn = tf.estimator.inputs.numpy_input_fn(
      x=trainer.model.feature_list_to_dict(X_test),
      y=np.array(y_test),
      num_epochs=None,
      batch_size=hparams.eval_batch_size,
      shuffle=False # Don't shuffle evaluation data
    )

    return tf.contrib.learn.Experiment(
      trainer.model.build_estimator(config=config),
      train_input_fn=train_input_fn,
      eval_input_fn=eval_input_fn,
      **experiment_args
    )
  return _experiment_fn


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
    default=40
  )
  parser.add_argument(
    '--eval-batch-size',
    help='Batch size for evaluation steps',
    type=int,
    default=40
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
    '--export-format',
    help='The input format of the exported SavedModel binary',
    choices=['JSON'],
    default='JSON'
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
  learn_runner.run(
    generate_experiment_fn(
      min_eval_frequency=args.min_eval_frequency,
      eval_delay_secs=args.eval_delay_secs,
      train_steps=args.train_steps,
      eval_steps=args.eval_steps,
      export_strategies=[saved_model_export_utils.make_export_strategy(
        trainer.model.SERVING_FUNCTIONS[args.export_format],
        exports_to_keep=1,
        default_output_alternative_key=None,
      )]
    ),
    run_config=run_config.RunConfig(model_dir=args.job_dir),
    hparams=hparam.HParams(**args.__dict__)
  )
