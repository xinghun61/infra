# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Includes all the constants of module names, queue names, url paths, etc."""

import os


# Names of all modules.
WATERFALL_BACKEND = 'waterfall-backend'
CRASH_BACKEND = {
    'fracas': 'crash-backend-fracas',
    'cracas': 'crash-backend-cracas',
    'clusterfuzz': 'crash-backend-clusterfuzz'
}


# Names of all queues.
DEFAULT_QUEUE = 'default'
WATERFALL_ANALYSIS_QUEUE = 'waterfall-analysis-queue'
WATERFALL_TRY_JOB_QUEUE = 'waterfall-try-job-queue'
WATERFALL_FAILURE_ANALYSIS_REQUEST_QUEUE = 'waterfall-failure-analysis-request'
WATERFALL_FLAKE_ANALYSIS_REQUEST_QUEUE = 'waterfall-flake-analysis-request'
CRASH_ANALYSIS_QUEUE = {
    'fracas': 'crash-analysis-fracas-queue',
    'cracas': 'crash-analysis-cracas-queue',
    'clusterfuzz': 'crash-analysis-clusterfuzz-queue'
}


# Waterfall-related.
WATERFALL_PROCESS_FAILURE_ANALYSIS_REQUESTS_URL = (
    '/waterfall/process-failure-analysis-requests')
WATERFALL_PROCESS_FLAKE_ANALYSIS_REQUEST_URL = (
    '/waterfall/process-flake-analysis-request')
WATERFALL_ALERTS_URL = 'https://sheriff-o-matic.appspot.com/alerts'
COMPILE_STEP_NAME = 'compile'


# TODO: move this to config.
# Whitelisted app ids for authorized access.
WHITELISTED_APP_ACCOUNTS = [
    'chromium-try-flakes@appspot.gserviceaccount.com',
    'findit-for-me@appspot.gserviceaccount.com',
]


# Directory of html templates.
HTML_TEMPLATE_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), os.path.pardir, 'templates'))

DEFAULT_SERVICE_ACCOUNT = 'findit-for-me@appspot.gserviceaccount.com'
