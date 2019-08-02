#!/bin/bash
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Change these values as required to set up new views.
APP_ID=sheriff-o-matic-staging

sed -e s/APP_ID/$APP_ID/g step_status_transitions.sql | bq --project $APP_ID query --use_legacy_sql=false
sed -e s/APP_ID/$APP_ID/g failing_steps.sql | bq query --project $APP_ID --use_legacy_sql=false
sed -e s/APP_ID/$APP_ID/g sheriffable_failures.sql | bq --project $APP_ID query --use_legacy_sql=false

