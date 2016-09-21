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
WATERFALL_SERIAL_QUEUE = 'waterfall-serial-queue'
CRASH_ANALYSIS_QUEUE = {
    'fracas': 'crash-analysis-fracas-queue',
    'cracas': 'crash-analysis-cracas-queue',
    'clusterfuzz': 'crash-analysis-clusterfuzz-queue'
}


# Waterfall-related.
WATERFALL_TRIGGER_ANALYSIS_URL = '/waterfall/trigger-analyses'
WATERFALL_ALERTS_URL = 'https://sheriff-o-matic.appspot.com/alerts'
COMPILE_STEP_NAME = 'compile'


# Directory of html templates.
HTML_TEMPLATE_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), os.path.pardir, 'templates'))
