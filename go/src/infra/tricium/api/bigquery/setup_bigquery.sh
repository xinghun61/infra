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
if ! (bqschemaupdater -force -message apibq.FeedbackEvent \
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

echo "- Create BigQuery views:"
echo ""
echo " - analyzer.analyzer_efficacy"
QUERY='WITH
  every AS (
    SELECT
      project,
      change,
      analyzer,
      SUM(num_included_comments) AS num_comments
    FROM
      (
        SELECT
          gerrit_revision.project,
          SPLIT(gerrit_revision.git_ref, "/")[OFFSET(3)] AS change,
          c.comment.path,
          c.analyzer,
          c.comment.category,
          c.comment.start_line,
          c.comment.end_line,
          c.comment.start_char,
          c.comment.end_char,
          COUNTIF(c.selected = TRUE) AS num_included_comments
        FROM
          `'${APPID}'.analyzer.results`,
          UNNEST(comments) AS c
        GROUP BY project, change, path, analyzer, category, start_line, end_line, start_char, end_char
      )
    GROUP BY project, change, analyzer
  ),
  last_revision AS (
    WITH
      last_revision AS (
        SELECT
          gerrit_revision.project,
          SPLIT(gerrit_revision.git_ref, "/")[OFFSET(3)] AS change,
          MAX(revision_number) AS revision
        FROM
          `'${APPID}'.analyzer.results`
        GROUP BY project, change
      )
    SELECT
      project,
      SPLIT(gerrit_revision.git_ref, "/")[OFFSET(3)] AS change,
      last_revision.revision,
      c.analyzer,
      COUNTIF(c.selected = TRUE) AS num_comments
    FROM
      `'${APPID}'.analyzer.results`,
      UNNEST(comments) AS c
      JOIN
      last_revision
      ON gerrit_revision.project = last_revision.project AND SPLIT(gerrit_revision.git_ref, "/")[OFFSET(3)] =
        last_revision.change AND revision_number = last_revision.revision
    GROUP BY project, change, revision, analyzer
  )
SELECT
  every.analyzer,
  SUM(every.num_comments) AS total_comments,
  SUM(last_revision.num_comments) AS final_comments,
  IF(SUM(every.num_comments) > 0, 1 - (SUM(last_revision.num_comments) / SUM(every.num_comments)), NULL) AS efficacy
FROM
  every
  JOIN
  last_revision
  ON every.project = last_revision.project AND every.analyzer = last_revision.analyzer
GROUP BY analyzer'
DESC="Overall analyzer efficacy for all selected comments."
if ! (bq mk --use_legacy_sql=false --view "${QUERY}" \
  --description "${DESC}" \
  --project_id "${APPID}" analyzer.analyzer_efficacy); then
  echo ""
  echo "The view already exists. You can delete it with:"
  echo ""
  echo "  bq rm ${APPID}:analyzer.analyzer_efficacy"
  echo ""
  echo "and run this script again."
  # Don't fail here.
fi

echo ""
echo " - analyzer.comment_latency"
QUERY='SELECT
  c.analyzer,
  requested_time,
  c.created_time,
  TIMESTAMP_DIFF(c.created_time, requested_time, SECOND) AS latency
FROM
  `'${APPID}'.analyzer.results`, UNNEST(comments) AS c
ORDER BY requested_time'
DESC="Latency for all comments."
if ! (bq mk --use_legacy_sql=false --view "${QUERY}" \
  --description "${DESC}" \
  --project_id "${APPID}" analyzer.comment_latency); then
  echo ""
  echo "The view already exists. You can delete it with:"
  echo ""
  echo "  bq rm ${APPID}:analyzer.comment_latency"
  echo ""
  echo "and run this script again."
  # Don't fail here.
fi

echo ""
echo " - analyzer.comment_selection"
QUERY='SELECT
  c.analyzer,
  c.created_time
FROM
  `'${APPID}'.analyzer.results`, UNNEST(comments) AS c
WHERE
  c.selected = TRUE
ORDER BY c.created_time'
DESC="The creation time and analyzer name for all selected comments"
if ! (bq mk --use_legacy_sql=false --view "${QUERY}" \
  --description "${DESC}" \
  --project_id "${APPID}" analyzer.comment_selection); then
  echo ""
  echo "The view already exists. You can delete it with:"
  echo ""
  echo "  bq rm ${APPID}:analyzer.comment_selection"
  echo ""
  echo "and run this script again."
  # Don't fail here.
fi
