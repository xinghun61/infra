# Monorail Machine Learning Classifiers

Monorail has two machine learning classifiers running in ML Engine: a spam classifier and a component predictor.

Whenever a user creates a new issue (or comments on an issue without an assigned component), components are suggested based on the text the user types using Monorail's component predictor.

Monorail also runs each new issue and comment through a spam classifier model.

In order to train a new model locally or in the cloud, follow the instructions below.

> Note: you must be logged into the correct GCP project with `gcloud` in order to run the below commands.

### Trainer

Both trainers are Python modules that do the following:

1. Download all (spam or component) exported training data from GCS
2. Define a TensorFlow Estimator and Experiment

ML Engine uses the high-level [`learn_runner`](https://www.tensorflow.org/api_docs/python/tf/contrib/learn/learn_runner/run) API (see [`trainer/task.py`](trainer/task.py)) which allows it to train, evaluate, and predict against a model saved in GCS.

## Monorail Spam Classifier

### Run locally

To test the trainer without waiting for it to download all its training data, you can download and supply some manually with the `--train-file` argument.

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
    --trainer-type spam
```

To have the trainer download all training data, you'll need to supply the
`--gcs-bucket` and `--gcs-prefix` arguments.

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
    --trainer-type spam
```

### Submit a local prediction

```sh
./spam.py local-predict
gcloud ml-engine local predict --model-dir $OUTPUT_DIR/export/Servo/{TIMESTAMP}/ --json-instances /tmp/instances.json
```

### Submitting a training job to ML Engine

This will run a job and output a trained model to GCS. Job names must be unique.

First verify you're in the `monorail-prod` GCP project.

```sh
gcloud init
```

To submit a training job manually, run:

```sh
TIMESTAMP=$(date +%s)
JOB_NAME=spam_trainer_$TIMESTAMP
gcloud ml-engine jobs submit training $JOB_NAME \
    --package-path trainer/ \
    --module-name trainer.task \
    --runtime-version 1.2 \
    --job-dir gs://monorail-prod-mlengine/$JOB_NAME \
    --region us-central1 \
    -- \
    --train-steps 1000 \
    --verbosity DEBUG \
    --gcs-bucket monorail-prod.appspot.com \
    --gcs-prefix spam_training_data
    --trainer-type spam
```

### Uploading a model and and promoting it to production

To upload a model you'll need to locate the exported model directory in GCS. To do that, run:

```sh
gsutil ls -r gs://monorail-prod-mlengine/$JOB_NAME

# Look for a directory that matches the below structure and assign it.
# It should have the structure $GCS_OUTPUT_LOCATION/export/Servo/$TIMESTAMP/.
MODEL_BINARIES=gs://monorail-prod-mlengine/spam_trainer_1507059720/export/Servo/1507060043/

VERSION=v_$TIMESTAMP
gcloud ml-engine versions create $VERSION \
    --model spam_only_words \
    --origin $MODEL_BINARIES \
    --runtime-version 1.2
```

To promote to production, set that model as default.

```sh
gcloud ml-engine versions set-default $VERSION --model spam_only_words
```

### Submit a prediction

Use the script [`spam.py`](spam.py) to make predictions
from the command line. Files containing text for classification must be provided as summary and content arguments.

```sh
$ ./spam.py predict --summary summary.txt --content content.txt
{u'predictions': [{u'classes': [u'0', u'1'], u'scores': [0.4986788034439087, 0.5013211965560913]}]}
```

A higher probability for class 1 indicates that the text was classified as spam.

### Compare model accuracy

After submitting a job to ML Engine, you can compare the accuracy of two submitted jobs using their trainer names.

```sh
$ ./spam.py --project monorail-prod compare-accuracy --model1 spam_trainer_1521756634 --model2 spam_trainer_1516759200
spam_trainer_1521756634:
AUC: 0.996436  AUC Precision/Recall: 0.997456

spam_trainer_1516759200:
AUC: 0.982159  AUC Precision/Recall: 0.985069
```

By default, model1 is the default model running in the specified project. Note that an error will be thrown if the trainer does not contain an eval_data.json file.

## Monorail Component Predictor

### Run locally

To kick off a local training job, run:

```sh
OUTPUT_DIR=/tmp/monospam-local-training
rm -rf $OUTPUT_DIR
gcloud ml-engine local train \
    --package-path trainer/ \
    --module-name trainer.task \
    --job-dir $OUTPUT_DIR \
    -- \
    --train-steps 10000 \
    --eval-steps 1000 \
    --verbosity DEBUG \
    --gcs-bucket monorail-prod.appspot.com \
    --gcs-prefix component_training_data \
    --trainer-type component
```

### Submitting a training job to ML Engine

This will run a job and output a trained model to GCS. Job names must be unique.

First verify you're in the `monorail-prod` GCP project.

```sh
gcloud init
```

To submit a training job manually, run:

```sh
TIMESTAMP=$(date +%s)
JOB_NAME=component_trainer_$TIMESTAMP
gcloud ml-engine jobs submit training $JOB_NAME \
    --package-path trainer/ \
    --module-name trainer.task \
    --runtime-version 1.2 \
    --job-dir gs://monorail-prod-mlengine/$JOB_NAME \
    --region us-central1 \
    --scale-tier custom \
    --config config.json \
    -- \
    --train-steps 10000 \
    --eval-steps 1000 \
    --verbosity DEBUG \
    --gcs-bucket monorail-prod.appspot.com \
    --gcs-prefix component_training_data \
    --trainer-type component
```

### Uploading a model and and promoting it to production

To upload a model you'll need to locate the exported model directory in GCS. To do that, run:

```sh
gsutil ls -r gs://monorail-prod-mlengine/$JOB_NAME

# Look for a directory that matches the below structure and assign it.
# It should have the structure $GCS_OUTPUT_LOCATION/export/Servo/$TIMESTAMP/.
MODEL_BINARIES=gs://monorail-prod-mlengine/component_trainer_1507059720/export/Servo/1507060043/

VERSION=v_$TIMESTAMP
gcloud ml-engine versions create $VERSION \
    --model component_top_words \
    --origin $MODEL_BINARIES \
    --runtime-version 1.2
```
To promote to production, set that model as default.

```sh
gcloud ml-engine versions set-default $VERSION --model component_top_words
```

### Submit a prediction

Use the script [`component.py`](component.py) to make predictions from the command line. A file containing text for classification must be provided as the content argument.

```sh
$ ./component.py --project monorail-prod --content content.txt
Most likely component: index 108, component id 36250211
```
