# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Predator for crash (ClusterFuzz & Fracas/Chromecrash) configuration."""

import re

from google.appengine.ext import ndb

from analysis.type_enums import CrashClient
from gae_libs.model.versioned_config import VersionedConfig


class CrashConfig(VersionedConfig):
  """Global configuration of settings for processing Chrome crashes."""
  # An example of fracas-specific parameters:
  # {
  #   'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
  #   'supported_platform_list_by_channel': {
  #     'canary': ['win', 'mac'],
  #   },
  #   'platform_rename': {
  #     'linux': 'unix'
  #   },
  #   'signature_blacklist_markers': [],
  # }
  fracas = ndb.JsonProperty(indexed=False, default={})

  # An example of cracas-specific parameters:
  # {
  #   'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
  #   'supported_platform_list_by_channel': {
  #     'canary': ['win', 'mac'],
  #   },
  #   'platform_rename': {
  #     'linux': 'unix'
  #   },
  #   'signature_blacklist_markers': [],
  # }
  cracas = ndb.JsonProperty(indexed=False, default={})

  # An example of cracas-specific parameters:
  # {
  #   'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
  #   'signature_blacklist_markers': [],
  #   'blacklist_crash_type': ['out-of-memory'],
  #   'top_n': 7
  # }
  clusterfuzz = ndb.JsonProperty(indexed=False, default={})

  # An example of uma-sampling-profiler-specific parameters:
  # {
  #   'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
  #   'signature_blacklist_markers': [],
  # }
  uma_sampling_profiler = ndb.JsonProperty(indexed=False, default={})

  ################## Settings shared by Fracas/Clusterfuzz. ##################
  # An example of project classifier settings:
  # {
  #   'host_directories': [
  #     'src/chrome/browser/resources/',
  #     'src/chrome/test/data/layout_tests/',
  #     'src/media/',
  #     'src/sdch/',
  #     'src/testing/',
  #     'src/third_party/WebKit/',
  #     'src/third_party/',
  #     'src/tools/',
  #     'src/'
  #   ],
  #   # Where there is no dep_path found, use function and file_path makers to
  #   # map a Result or StackFrame to a project name.
  #     'function_marker_to_project_name': {
  #       'org.chromium': 'chromium',
  #       'com.google.android.apps.chrome': 'clank',
  #       'android.': 'android_os',
  #       'com.android.': 'android_os',
  #   },
  #   'file_path_marker_to_project_name': {
  #     ('https___googleplex-android.googlesource.'
  #      'com_a_platform_manifest.git/'): 'android_os',
  #     'googleplex-android/': 'android_os',
  #   },
  #
  #   # Number of frames on top to consider when deciding the crashed project.
  #   'top_n': 4,
  #
  #   # The chromium project should always have the highest rank priority (0).
  #   # This dict assigns rank priorities to non chromium projects.
  #   'non_chromium_project_rank_priority' = {
  #     'clank': -1,
  #     'android_os': -2,
  #     'android_os_java': -2,
  #     'src_internal': -3,
  #     'others': -4,
  #   }
  # }
  project_classifier = ndb.JsonProperty(indexed=False, default={})

  # An example of component classifier settings:
  # {
  #   # Number of frames on top to consider when deciding the crashed
  #   #component.
  #   'top_n': 4,
  #   'path_function_component': [
  #     [r'src/third_party/WebKit/Source/core/layout', , 'Blink>Layout'],
  #     ...
  #   ]
  # }
  component_classifier = ndb.JsonProperty(indexed=False, default={},
                                          compressed=True)

  # A mapping from repo_url to dep_path.
  repo_to_dep_path = ndb.JsonProperty(indexed=False, default={},
                                      compressed=True)

  # Configurations for feature_options.
  feature_options = ndb.JsonProperty(indexed=False, default={},
                                     compressed=True)

  def GetClientConfig(self, client_id):
    """Gets client specific config using client_id."""
    if client_id == CrashClient.FRACAS:
      return self.fracas
    elif client_id == CrashClient.CRACAS:  # pragma: no cover.
      return self.cracas
    elif client_id == CrashClient.CLUSTERFUZZ:  # pragma: no cover.
      return self.clusterfuzz
    elif client_id == CrashClient.UMA_SAMPLING_PROFILER:
      return self.uma_sampling_profiler
    return None
