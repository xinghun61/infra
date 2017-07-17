# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import urllib

from analysis.type_enums import CrashClient
from common.model.crash_analysis import CrashAnalysis
from google.appengine.ext import ndb

_UMA_SAMPLING_PROFILER_URL_TEMPLATE = (
    'https://uma.googleplex.com/p/chrome/callstacks?q=%s')

_PROCESS_TYPE_TO_INT = {
    'UNKNOWN_PROCESS': 0,
    'BROWSER_PROCESS': 1,
    'RENDERER_PROCESS': 2,
    'GPU_PROCESS': 3,
    'UTILITY_PROCESS': 4,
    'ZYGOTE_PROCESS': 5,
    'SANDBOX_HELPER_PROCESS': 6,
    'PPAPI_PLUGIN_PROCESS': 7,
    'PPAPI_BROKER_PROCESS': 8,
}

_CHANNEL_TO_INT = {
    'canary': 1, 'dev': 2, 'beta': 3, 'stable': 4
}

# TODO(cweakliam): Rename CrashAnalysis to something more generic now that
# Predator deals with regressions as well as crashes


class UMASamplingProfilerAnalysis(CrashAnalysis):
  """Represents an analysis of a UMA Sampling Profiler Regression."""
  # customized properties for UMA regression.
  process_type = ndb.StringProperty()
  startup_phase = ndb.StringProperty()
  thread_type = ndb.StringProperty()
  collection_trigger = ndb.StringProperty()
  chrome_releases = ndb.JsonProperty()
  subtree_id = ndb.StringProperty()
  subtree_root_depth = ndb.IntegerProperty()
  subtree_stacks = ndb.JsonProperty()

  def Reset(self):
    super(UMASamplingProfilerAnalysis, self).Reset()
    self.process_type = None
    self.startup_phase = None
    self.thread_type = None
    self.collection_trigger = None
    self.chrome_releases = None
    self.subtree_id = None
    self.subtree_root_depth = None
    self.subtree_stacks = None

  def Initialize(self, regression_data):
    """(Re)Initializes a CrashAnalysis ndb.Model.

    Args:
      regression_data (UMASamplingProfilerData): the data used to initialize the
        analysis.
    """
    super(UMASamplingProfilerAnalysis, self).Initialize(regression_data)
    self.process_type = regression_data.process_type
    self.startup_phase = regression_data.startup_phase
    self.thread_type = regression_data.thread_type
    self.collection_trigger = regression_data.collection_trigger
    self.chrome_releases = regression_data.chrome_releases
    self.subtree_id = regression_data.subtree_id
    self.subtree_root_depth = regression_data.subtree_root_depth
    self.subtree_stacks = regression_data.subtree_stacks

  @property
  def client_id(self):
    return CrashClient.UMA_SAMPLING_PROFILER

  @property
  def crash_url(self):
    process_number = _PROCESS_TYPE_TO_INT[self.process_type]
    primary_version = self.chrome_releases[1]['version']
    secondary_version = self.chrome_releases[0]['version']
    primary_channel_number = _CHANNEL_TO_INT[self.chrome_releases[1]['channel']]
    secondary_channel_number = (
        _CHANNEL_TO_INT[self.chrome_releases[0]['channel']])
    params = {
        'editor': {
            'primarySelector': {
                'process': str(process_number),
                'release': '%s %s' % (primary_version,
                                      primary_channel_number)
            },
            'secondarySelector': {
                'process': str(process_number),
                'release': '%s %s' % (secondary_version,
                                      secondary_channel_number)
            },
            'displayDiff': True
        },
        'visualizer': {
          'flame_view_model': {
              'flame_graph_model': {
                  'zoom_to_node': self.subtree_id
              }
          }
        }
    }
    return (_UMA_SAMPLING_PROFILER_URL_TEMPLATE
            % urllib.quote(json.dumps(params)))

  @property
  def customized_data(self):
    return {
        'process_type': self.process_type,
        'startup_phase': self.startup_phase,
        'thread_type': self.thread_type,
        'collection_trigger': self.collection_trigger,
        'chrome_releases': self.chrome_releases,
        'subtree_id': self.subtree_id,
        'subtree_root_depth': self.subtree_root_depth,
        'subtree_stacks': self.subtree_stacks,
    }

  def ToJson(self):
    """Generate the original Json dict sent from UMA Sampling Profiler."""
    output_json = {
        'platform': self.platform,
        'process_type': self.process_type,
        'thread_type': self.thread_type,
        'collection_trigger': self.collection_trigger,
        'chrome_releases': self.chrome_releases,
        'subtree_root_depth': self.subtree_root_depth,
        'subtree_id': self.subtree_id,
        'subtree_stacks': self.subtree_stacks,
    }
    if self.startup_phase:
        output_json['startup_phase'] = self.startup_phase
    return output_json
