# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os


CRASH_BACKEND = {
    'fracas': 'crash-backend-fracas',
    'cracas': 'crash-backend-cracas',
    'clusterfuzz': 'crash-backend-clusterfuzz'
}


CRASH_ANALYSIS_QUEUE = {
    'fracas': 'crash-analysis-fracas-queue',
    'cracas': 'crash-analysis-cracas-queue',
    'clusterfuzz': 'crash-analysis-clusterfuzz-queue'
}


DEFAULT_QUEUE = 'default'


# Directory of html templates.
HTML_TEMPLATE_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), os.path.pardir, 'frontend',
                 'templates'))
