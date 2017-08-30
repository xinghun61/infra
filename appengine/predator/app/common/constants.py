# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from analysis.type_enums import CrashClient


CRASH_BACKEND = {
    CrashClient.FRACAS: 'backend-fracas',
    CrashClient.CRACAS: 'backend-cracas',
    CrashClient.CLUSTERFUZZ: 'backend-clusterfuzz',
    CrashClient.UMA_SAMPLING_PROFILER: 'backend-uma-sampling-profiler',
}


CRASH_ANALYSIS_QUEUE = {
    CrashClient.FRACAS: 'fracas-analysis-queue',
    CrashClient.CRACAS: 'cracas-analysis-queue',
    CrashClient.CLUSTERFUZZ: 'clusterfuzz-analysis-queue',
    CrashClient.UMA_SAMPLING_PROFILER: 'uma-sampling-profiler-analysis-queue',
}


DEFAULT_QUEUE = 'default'


# Directory of html templates.
HTML_TEMPLATE_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), os.path.pardir, 'frontend',
                 'templates'))
