# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from analysis.crash_data import CrashData
from analysis.dependency_analyzer import DependencyAnalyzer
from analysis.uma_sampling_profiler_parser import UMASamplingProfilerParser
from decorators import cached_property

# TODO(cweakliam): Rename CrashData to something more generic now that Predator
# deals with regressions as well as crashes


class UMASamplingProfilerData(CrashData):
  """Data about a performance regression/improvement from UMA Sampling Profiler.

  Properties:
    identifiers (dict): The key value pairs to uniquely identify a
      ``CrashData``.
    crashed_version (str): The version of project in which the regression
      occurred.
    signature (str): The signature of the regression.
    platform (str): The platform name; e.g., 'win', 'mac', 'linux', 'android',
      'ios', etc.
    stacktrace (Stacktrace): Collection of call stacks storing data about the
      functions involved in the regression.
    regression_range (pair or None): a pair of the last-good and first-bad
      versions.
    dependencies (dict): A dict from dependency paths to
      ``Dependency`` objects. The keys are all those deps which are
      used by both the ``crashed_version`` of the code, and at least
      one frame in the ``stacktrace.stacks``.
    dependency_rolls (dict) A dict from dependency
      paths to ``DependencyRoll`` objects. The keys are all those
      dependencies which (1) occur in the regression range for the
      ``platform`` where the regression occurred, (2) neither add nor delete
      a dependency, and (3) are also keys of ``dependencies``.
  """

  def __init__(self, regression_data, dep_fetcher):
    """Initialize with raw data sent by UMA Sampling Profiler.

    Args:
      regression_data (dict): Dicts sent through Pub/Sub by UMA Sampling
      Profiler. For example:
      {
        'platform': 'win',
        'process_type': 'BROWSER_PROCESS',
        # this field may not be present, depending on the collection_trigger:
        'startup_phase': 'MAIN_LOOP_START',
        'thread_type': 'UI_THREAD',
        'collection_trigger': 'PROCESS_STARTUP',
        'chrome_releases': [
           {'version': '54.0.2834.0', 'channel': 'canary'},
           {'version': '54.0.2835.0', 'channel': 'canary'},
        ],
        # Depth of the root of the subtree in the stacks, with the root at depth
        # 0:
        'subtree_root_depth': 19,
        # Unique identifier for the subtree:
        'subtree_id': 'AEF6F487C2EE7935',
        # Id of the subtree root function:
        'subtree_root_id': '9F4E0F78CF2B2668',
        # Ids of the significant changed nodes under the root.  In the case of a
        # renamed function, one id will be present for the old function and one
        # for the new function:
        'subtree_change_ids': ['EEC7F9CAAE0BDE58','817FAD6EAEBCCF14'],
        'subtree_stacks': [<list of stacks in dict form>],
      }
      dep_fetcher (ChromeDependencyFetcher): Dependency fetcher that can fetch
        all dependencies related to a regression version.
    """
    self._platform = regression_data['platform']
    self.process_type = regression_data['process_type']
    # startup_phase may not be present, depending on the collection_trigger
    self.startup_phase = regression_data.get('startup_phase')
    self.thread_type = regression_data['thread_type']
    self.collection_trigger = regression_data['collection_trigger']
    self.chrome_releases = regression_data['chrome_releases']
    # Unique identifier for the subtree:
    self.subtree_id = regression_data['subtree_id']
    self.subtree_root_id = regression_data['subtree_root_id']
    self.subtree_change_ids = regression_data['subtree_change_ids']
    # Depth of the root of the subtree in the stacks, with the root at depth 0:
    self.subtree_root_depth = regression_data['subtree_root_depth']
    self.subtree_stacks = regression_data['subtree_stacks']
    self._crashed_version = regression_data['chrome_releases'][1]['version']
    self._raw_stacktrace = ''
    self._dependency_analyzer = DependencyAnalyzer(self._platform,
                                                   self._crashed_version,
                                                   self.regression_range,
                                                   dep_fetcher)
    self._redo = regression_data.get('redo', False)

  @cached_property
  def stacktrace(self):
    """Parses ``subtree_stacks`` dict and returns ``Stacktrace`` object."""
    stacktrace = UMASamplingProfilerParser().Parse(
        self.subtree_stacks, self.subtree_root_depth,
        self._dependency_analyzer.regression_version_deps)
    if not stacktrace:
      logging.warning('Failed to parse the stacktrace %s',
                      self.subtree_stacks)
    return stacktrace

  @property
  def regression_range(self):
    """Pair of versions between which the regression/improvement occurred."""
    before = self.chrome_releases[0]['version']
    after = self.chrome_releases[1]['version']
    return before, after

  @cached_property
  def dependencies(self):
    """Get all dependencies that are in the stacktrace."""
    return self._dependency_analyzer.GetDependencies(
        self.stacktrace.stacks if self.stacktrace else [])

  @cached_property
  def dependency_rolls(self):
    """Gets all dependency rolls of ``dependencies`` in regression range."""
    return self._dependency_analyzer.GetDependencyRolls(
        self.stacktrace.stacks if self.stacktrace else [])

  @property
  def identifiers(self):
    return {'platform': self.platform,
            'process_type': self.process_type,
            'thread_type': self.thread_type,
            'collection_trigger': self.collection_trigger,
            'startup_phase': self.startup_phase,
            'chrome_releases': self.chrome_releases,
            'subtree_id': self.subtree_id}

  @property
  def signature(self):
    subtree_root = self.subtree_stacks[0]['frames'][self.subtree_root_depth]
    return subtree_root['function_name']
