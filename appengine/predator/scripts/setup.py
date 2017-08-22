# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Shared setup and configuration code for Predator scripts."""

from datetime import date
from datetime import timedelta
import os

from analysis.type_enums import CrashClient


# Determines which App Engine datastore is queried for entities.
DEFAULT_APP_ID = 'predator-for-me'
DEFAULT_CLIENT = CrashClient.CRACAS

# The max number of entities to query from App Engine at one time.
# App Engine APIs will fail if batch size is more than 1000.
MAX_BATCH_SIZE = 1000
DEFAULT_BATCH_SIZE = MAX_BATCH_SIZE

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
PREDATOR_RESULTS_DIRECTORY = os.path.join(_SCRIPT_DIR, '.predator_results')

_DATETIME_FORMAT = '%Y-%m-%d'
TODAY = date.today().strftime(_DATETIME_FORMAT)
A_YEAR_AGO = (date.today() - timedelta(days=365)).strftime(_DATETIME_FORMAT)