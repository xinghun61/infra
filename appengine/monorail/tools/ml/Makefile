# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# Or at https://developers.google.com/open-source/licenses/bsd

# Use 'make help' for a list of commands.

OUTPUT_DIR := /tmp/monospam-local-training/
TIMESTAMP := $(shell date +%s)
MODEL_DIR := /tmp/monospam-local-training/export/Servo/{TIMESTAMP}/
SPAM_JOB_NAME := spam_trainer_$(TIMESTAMP)
COMP_JOB_NAME := comp_trainer_$(TIMESTAMP)

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_.]*:/s/:.*//p' <Makefile

train_local_spam:
ifndef TRAIN_FILE
	$(error TRAIN_FILE not set)
endif
	gcloud ml-engine local train \
		--package-path trainer/ \
		--module-name trainer.task \
		--job-dir $(OUTPUT_DIR) \
		-- \
		--train-steps 1000 \
		--verbosity DEBUG \
		--train-file $(TRAIN_FILE) \
		--trainer-type spam

predict_local_spam:
	./spam.py local-predict
	gcloud ml-engine local predict \
		--model-dir $(MODEL_DIR) \
		--json-instances /tmp/instances.json

train_from_prod_data_spam:
	gcloud ml-engine local train \
		--package-path trainer/ \
		--module-name trainer.task \
		--job-dir $(OUTPUT_DIR) \
		-- \
		--train-steps 1000 \
		--verbosity DEBUG \
		--gcs-bucket monorail-prod.appspot.com \
		--gcs-prefix spam_training_data \
		--trainer-type spam

submit_train_job_spam:
	@echo ${TIMESTAMP}
	gcloud ml-engine jobs submit training $(SPAM_JOB_NAME) \
		--package-path trainer/ \
		--module-name trainer.task \
		--runtime-version 1.2 \
		--job-dir gs://monorail-prod-mlengine/$(SPAM_JOB_NAME) \
		--region us-central1 \
		-- \
		--train-steps 1000 \
		--verbosity DEBUG \
		--gcs-bucket monorail-prod.appspot.com \
		--gcs-prefix spam_training_data \
		--trainer-type spam

# VERSION of format 'v_TIMESTAMP' should match TIMESTAMP in SPAM_JOB_NAME and MODEL_BINARIES.
upload_model_prod_spam:
ifndef MODEL_BINARIES
	$(error MODEL_BINARIES not set)
endif
ifndef VERSION
	$(error VERSION not set)
endif
	gsutil ls -r gs://monorail-prod-mlengine/$(SPAM_JOB_NAME)
	gcloud ml-engine versions create $(VERSION) \
		--model spam_only_words \
		--origin $(MODEL_BINARIES) \
		--runtime-version 1.2
	gcloud ml-engine versions set-default $(VERSION) --model spam_only_words

submit_pred_spam:
ifndef SUMMARY_PATH
	$(error SUMMARY_PATH not set)
endif
ifndef CONTENT_PATH
	$(error CONTENT_PATH not set)
endif
	./spam.py predict --summary $(SUMMARY_PATH) --content $(CONTENT_PATH)


train_from_prod_data_component:
	gcloud ml-engine local train \
		--package-path trainer/ \
		--module-name trainer.task \
		--job-dir $(OUTPUT_DIR) \
		-- \
		--train-steps 10000 \
		--eval-steps 1000 \
		--verbosity DEBUG \
		--gcs-bucket monorail-prod.appspot.com \
		--gcs-prefix component_training_data \
		--trainer-type component

submit_train_job_component:
	gcloud init
	gcloud ml-engine jobs submit training $(COMP_JOB_NAME) \
		--package-path trainer/ \
		--module-name trainer.task \
		--runtime-version 1.2 \
		--job-dir gs://monorail-prod-mlengine/$(COMP_JOB_NAME) \
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

# VERSION of format 'v_TIMESTAMP' should match TIMESTAMP in COMP_JOB_NAME and MODEL_BINARIES.
upload_model_prod_component:
ifndef MODEL_BINARIES
	$(error MODEL_BINARIES not set)
endif
ifndef VERSION
	$(error VERSION not set)
endif
	gsutil ls -r gs://monorail-prod-mlengine/$(COMP_JOB_NAME)
	gcloud ml-engine versions create $(VERSION) \
		--model component_top_words \
		--origin $(MODEL_BINARIES) \
		--runtime-version 1.2
	gcloud ml-engine versions set-default $(VERSION) --model component_top_words

submit_pred_component:
ifndef CONTENT_PATH
	$(error CONTENT_PATH not set)
endif
	./component.py --project monorail-prod --content $(CONTENT_PATH)


### Local Training in TF 2.0

tf2_train_local_spam:
ifndef TRAIN_FILE
	$(error TRAIN_FILE not set)
endif
	python3 ./trainer2/task.py \
		--train-file $(TRAIN_FILE) \
		--job-dir $(OUTPUT_DIR) \
		--train-steps 1000 \
		--verbosity DEBUG \
		--trainer-type spam

tf2_train_local_component:
ifndef TRAIN_FILE
	$(error TRAIN_FILE not set)
endif
	python3 ./trainer2/task.py \
		--train-file $(TRAIN_FILE) \
		--job-dir $(OUTPUT_DIR) \
		--train-steps 10000 \
		--eval-steps 1000 \
		--verbosity DEBUG \
		--trainer-type component
