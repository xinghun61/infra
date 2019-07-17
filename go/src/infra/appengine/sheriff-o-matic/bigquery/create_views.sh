#!/bin/bash
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Change these values as required to set up new views.
APP_ID=sheriff-o-matic-staging
PROJECT=chromium

sed -e s/APP_ID/$APP_ID/g -e s/PROJECT/$PROJECT/g step_status_transitions.sql | bq query --use_legacy_sql=false
sed -e s/APP_ID/$APP_ID/g -e s/PROJECT/$PROJECT/g failing_steps.sql | bq query --use_legacy_sql=false
sed -e s/APP_ID/$APP_ID/g -e s/PROJECT/$PROJECT/g sheriffable_failures.sql | bq query --use_legacy_sql=false

