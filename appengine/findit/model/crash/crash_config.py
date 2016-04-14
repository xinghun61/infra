# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Findit for crash (ClusterFuzz & Fracas/Chromecrash) configuration."""

from google.appengine.ext import ndb

from model.versioned_config import VersionedConfig


class CrashConfig(VersionedConfig):
  """Global configuration of settings for processing Chrome crashes."""
  # Fracas-specific parameters.
  # {
  #   "crash_data_push_token": "secret_token",
  #   "analysis_result_pubsub_topic": "projects/project-name/topics/name",
  #   "supported_platform_list_by_channel": {
  #     "canary": ["win", "mac"],
  #   },
  # }
  fracas = ndb.JsonProperty(indexed=False, default={})
