#!/bin/bash
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -eu

cd "$(dirname $0)"

if ! (which bq) > /dev/null; then
  echo "Please install 'bq' from gcloud SDK"
  echo "  https://cloud.google.com/sdk/install"
  exit 1
fi

if ! (which bqschemaupdater) > /dev/null; then
  echo "Please install 'bqschemaupdater' from Chrome's infra.git"
  echo "  Checkout infra.git then run: eval $(../../../../../env.py)"
  exit 1
fi

if [ $# != 1 ]; then
  echo "usage: setup_bigquery.sh <instanceid>"
  echo ""
  echo "Pass one argument which is the instance name"
  exit 1
fi

APPID="$1"
SERVICEACCT="${APPID//:/.}"

echo "- Make sure the BigQuery API is enabled for the project:"
# It is enabled by default for new projects, but it wasn't for older projects.
gcloud services enable --project "${APPID}" bigquery-json.googleapis.com


# TODO(qyearsley): The stock role "roles/bigquery.dataEditor" grants
# more permissions than necessary. Ideally we should also create a custom
# role here programmatically. The new role may only need access to
# "bigquery.tables.updateData".
# Creating such a role using the gcloud command involves defining the role in a
# separate yaml file; see:
# https://cloud.google.com/iam/docs/creating-custom-roles#iam-custom-roles-create-gcloud
# https://cloud.google.com/iam/docs/understanding-custom-roles

# https://cloud.google.com/iam/docs/granting-roles-to-service-accounts
# https://cloud.google.com/bigquery/docs/access-control
echo "- Grant access to the AppEngine app to the role account:"
gcloud projects add-iam-policy-binding "${APPID}" \
    --member "serviceAccount:${SERVICEACCT}@appspot.gserviceaccount.com" \
    --role roles/bigquery.dataEditor


echo "- Create the datasets:"
echo ""
echo "  Warning: On first 'bq' invocation, it'll try to find out default"
echo "    credentials and will ask to select a default app; just press enter to"
echo "    not select a default."

# Optional: --default_table_expiration 63244800
if ! (bq --location=US mk --dataset --description "Analysis result statistics" \
  "${APPID}:analyzer"); then
  echo ""
  echo "Dataset creation failed. Assuming the dataset already exists. At worst"
  echo "the following command(s) will fail."
fi
if ! (bq --location=US mk --dataset --description "Events and user actions" \
  "${APPID}:events"); then
  echo ""
  echo "Dataset creation failed. Assuming the dataset already exists. At worst"
  echo "the following command(s) will fail."
fi


echo "- Populate the BigQuery schema for the tables:"
echo ""
echo "  Warning: On first 'bqschemaupdater' run, it will request default"
echo "    credentials, which are stored independently from 'bq' permissions."
if ! (bqschemaupdater -force -message apibq.AnalysisRun \
  -table "${APPID}.analyzer.results"); then
  echo ""
  echo ""
  echo "Oh no! You may need to restart from scratch. You can do so with:"
  echo ""
  echo "  bq rm ${APPID}:analyzer.results"
  echo ""
  echo "and run this script again."
  exit 1
fi
if ! (bqschemaupdater -force -message apibq.Event \
  -table "${APPID}.events.feedback"); then
  echo ""
  echo ""
  echo "Oh no! You may need to restart from scratch. You can do so with:"
  echo ""
  echo "  bq rm ${APPID}:events.feedback"
  echo ""
  echo "and run this script again."
  exit 1
fi

cd -
