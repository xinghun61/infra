# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging


class DependencyAnalyzer(object):

  def __init__(self, platform, regression_version, regression_range,
               dep_fetcher):
    """Data about the dependencies relating to a crash/regression.

    Properties:
      _platform (str): The platform name; e.g., 'win', 'mac', 'linux',
        'android', 'ios', etc.
      _regression_version (str): The version of project in which the
        crash/regression occurred.
      _regression_range (pair or None): a pair of the last-good and first-bad
        versions.
      _dependencies (dict): A dict from dependency paths to
        ``Dependency`` objects. The keys are all those deps which are
        used by both the ``regression_version`` of the code, and at least
        one frame in the relevant ``stacktrace`` stacks.
      _dependency_rolls (dict) A dict from dependency
        paths to ``DependencyRoll`` objects. The keys are all those
        dependencies which (1) occur in the regression range for the
        ``platform`` where the crash occurred, (2) neither add nor delete
        a dependency, and (3) are also keys of ``dependencies``.
      _dep_fetcher (ChromeDependencyFetcher): Dependency fetcher that can fetch
        all dependencies related to regression_version.
    """
    self._platform = platform
    self._regression_version = regression_version
    self._regression_range = regression_range
    self._dep_fetcher = dep_fetcher

    self._regression_version_deps = None

  def GetDependencies(self, stacks_list):
    """Get all dependencies that are in the given stacks."""
    if not stacks_list:
      logging.warning('Cannot get dependencies without stacktrace.')
      return {}

    return {
        frame.dep_path: self.regression_version_deps[frame.dep_path]
        for stack in stacks_list
        for frame in stack.frames
        if frame.dep_path and frame.dep_path in self.regression_version_deps
    }

  def GetDependencyRolls(self, stacks_list):
    """Gets all dependency rolls of ``dependencies`` in regression range."""
    # Short-circuit when we know the deprolls must be empty.
    if not self._regression_range or not stacks_list:
      logging.warning('Cannot get deps and dep rolls for report without '
                      'regression range or stacktrace.')
      return {}

    # Get ``DependencyRoll` objects for all dependencies in the regression
    # range (for this particular platform).
    regression_range_dep_rolls = self._dep_fetcher.GetDependencyRollsDict(
        self._regression_range[0], self._regression_range[1], self._platform)
    # Filter out the ones which add or delete a dependency, because we
    # can't really be sure whether to blame them or not. This rarely
    # happens, so our inability to decide shouldn't be too much of a problem.
    def HasBothRevisions(dep_path, dep_roll):
      has_both_revisions = bool(dep_roll.old_revision) and bool(
          dep_roll.new_revision)
      if not has_both_revisions:
        logging.info(
            'Skip %s dependency %s',
            'added' if dep_roll.new_revision else 'deleted',
            dep_path)
      return has_both_revisions

    # Apply the above filter, and also filter to only retain those
    # which occur in ``GetDependencies``.
    return {
        dep_path: dep_roll
        for dep_path, dep_roll in regression_range_dep_rolls.iteritems()
        if HasBothRevisions(dep_path, dep_roll) and dep_path
        in self.GetDependencies(stacks_list)
    }

  @property
  def regression_version_deps(self):
    """Gets all dependencies related to regression_version.

    N.B. All dependencies will be returned, no matter whether they appeared in
    stacktrace or are related to the crash/regression or not.
    """
    if self._regression_version_deps:
      return self._regression_version_deps

    self._regression_version_deps = self._dep_fetcher.GetDependency(
        self._regression_version, self._platform) if self._dep_fetcher else {}

    return self._regression_version_deps

