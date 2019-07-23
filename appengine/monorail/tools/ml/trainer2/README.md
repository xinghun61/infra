### Trainer

## Monorail Spam Classifier

To have the trainer run locally, you'll need to supply the
`--train-file` arguments.

```sh
TRAIN_FILE=./spam_training_examples.csv
OUTPUT_DIR=/tmp/monospam-local-training/
rm -rf $OUTPUT_DIR
python3 ./task.py \
    --train-file $TRAIN_FILE \
    --job-dir $OUTPUT_DIR \
    --train-steps 1000 \
    --verbosity DEBUG \
    --trainer-type spam
```
## Monorail Component Predictor

To have the trainer run locally, you'll need to supply the
`--train-file` arguments.

```sh
TRAIN_FILE=./component_training_examples.csv
OUTPUT_DIR=/tmp/monospam-local-training/
rm -rf $OUTPUT_DIR
python3 ./task.py \
    --train-file $TRAIN_FILE \
    --job-dir $OUTPUT_DIR \
    --train-steps 10000 \
    --eval-steps 1000 \
    --verbosity DEBUG \
    --trainer-type component
```