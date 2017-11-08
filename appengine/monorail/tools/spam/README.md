# Monorail Spam Classifier

Monorail runs each new issue and comment through a spam classifier model running in ML Engine.

In order to train a new model locally or in the cloud, follow the instructions below.

> Note: you must be logged into the correct GCP project with `gcloud`
> in order to run the below commands.

## Trainer

The trainer is a Python module that does the following:

1. Download all spam export training data from GCS
2. Define a TensorFlow Estimator and Experiment

ML Engine uses the high-level
[`learn_runner`](https://www.tensorflow.org/api_docs/python/tf/contrib/learn/learn_runner/run)
API (see [`trainer/task.py`](trainer/task.py)) which allows it to train, evaluate,
and predict against a model saved in GCS.

### Run locally

To test the trainer without waiting for it to download all its training data, you
can download and supply some manually with the `--train-file` argument.

```sh
TRAIN_DATA_DIR={fill this in}
gsutil cp gs://monorail-staging-mlengine/data/spam_training_data/2017-09-14 $TRAIN_DATA_DIR
```

To kick off the local job, run:

```sh
OUTPUT_DIR=/tmp/monospam-local-training
rm -rf $OUTPUT_DIR
gcloud ml-engine local train \
    --package-path trainer/ \
    --module-name trainer.task \
    --job-dir $OUTPUT_DIR \
    -- \
    --train-steps 1000 \
    --verbosity DEBUG \
    --train-file $TRAIN_DATA_DIR/2017-09-14
```

To have the trainer download all training data, you'll need to supply the
`--gcs-bucket` and --gcs-prefix` arguments.

```sh
OUTPUT_DIR=/tmp/monospam-local-training
rm -rf $OUTPUT_DIR
gcloud ml-engine local train \
    --package-path trainer/ \
    --module-name trainer.task \
    --job-dir $OUTPUT_DIR \
    -- \
    --train-steps 1000 \
    --verbosity DEBUG \
    --gcs-bucket monorail-prod.appspot.com \
    --gcs-prefix spam_training_data
```

### Submit a local prediction

```sh
./spam.py local-predict
gcloud ml-engine local predict --model-dir $OUTPUT_DIR/export/Servo/{TIMESTAMP}/ --json-instances /tmp/instances.json
```

### Submitting a training job to ML Engine

This will run a job and output a trained model to GCS. Job names must be unique.
To submit a training job manually, run:

```sh
TIMESTAMP=$(date +%s)
JOB_NAME=spam_trainer_$TIMESTAMP
gcloud ml-engine jobs submit training $JOB_NAME \
    --package-path trainer/ \
    --module-name trainer.task \
    --runtime-version 1.2 \
    --job-dir gs://monorail-staging-mlengine/$JOB_NAME \
    --region us-central1 \
    -- \
    --train-steps 1000 \
    --verbosity DEBUG \
    --gcs-bucket monorail-staging.appspot.com \
    --gcs-prefix spam_training_data
```

### Uploading a model and and promoting it to production

To upload a model you'll need to locate the exported model directory in GCS.
To do that, run:

```sh
gsutil ls -r gs://monorail-staging-mlengine/$JOB_NAME

# Look for a directory that matches the below structure and assign it.
# It should have the structure $GCS_OUTPUT_LOCATION/export/Servo/$TIMESTAMP/.
MODEL_BINARIES=gs://monorail-staging-mlengine/spam_trainer_1507059720/export/Servo/1507060043/

VERSION=v_$TIMESTAMP
gcloud ml-engine versions create $VERSION \
    --model spam \
    --origin $MODEL_BINARIES \
    --runtime-version 1.2
```

To promote to production, set that model as default.

```sh
gcloud ml-engine versions set-default $VERSION --model spam
```

## Submit a prediction

Use the script [`test_prediction.py`](test_prediction.py) to make predictions
from the command line. It will prompt for a subject and content.

```sh
$ ./spam.py predict
Summary: A summary that might be spam
Description: A description that may or may not be spam
{u'predictions': [{u'classes': [u'0', u'1'], u'scores': [0.4986788034439087, 0.5013211965560913]}]}
```
