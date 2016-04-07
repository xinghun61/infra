# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Includes all the constants of module names, queue names, url paths, etc."""

# Names of all modules.
WATERFALL_BACKEND = 'waterfall-backend'


# Names of all queues.
DEFAULT_QUEUE = 'default'
WATERFALL_ANALYSIS_QUEUE = 'waterfall-analysis-queue'
WATERFALL_TRY_JOB_QUEUE = 'waterfall-try-job-queue'
WATERFALL_SERIAL_QUEUE = 'waterfall-serial-queue'


# Url paths.
WATERFALL_TRIGGER_ANALYSIS_URL = '/waterfall/trigger-analyses'
WATERFALL_ALERTS_URL = 'https://sheriff-o-matic.appspot.com/alerts'
