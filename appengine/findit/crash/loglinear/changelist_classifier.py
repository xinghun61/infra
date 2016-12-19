# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import math

from common import chrome_dependency_fetcher
from crash import changelist_classifier
from crash.loglinear.changelist_features import min_distance
from crash.loglinear.changelist_features import top_frame_index
from crash.loglinear.model import ToFeatureFunction
from crash.loglinear.model import UnnormalizedLogLinearModel
from crash.stacktrace import CallStack
from crash.stacktrace import Stacktrace


class LogLinearChangelistClassifier(object):
  """A ``LogLinearModel``-based implementation of CL classification."""

  def __init__(self, repository, weights, top_n_frames=7, top_n_suspects=3):
    """Args:
      repository (Repository): the Git repository for getting CLs to classify.
      weights (dict of float): the weights for the features. The keys of
        the dictionary are the names of the feature that weight is
        for. We take this argument as a dict rather than as a list so that
        callers needn't worry about what order to provide the weights in.
      top_n_frames (int): how many frames of each callstack to look at.
      top_n_suspects (int): maximum number of suspects to return.
    """
    self._repository = repository
    self._top_n_frames = top_n_frames
    self._top_n_suspects = top_n_suspects

    feature_function = ToFeatureFunction([
        top_frame_index.TopFrameIndexFeature(top_n_frames),
        min_distance.MinDistanceFeature(),
    ])

    weight_list = [
        weights['TopFrameIndex'],
        weights['MinDistance'],
    ]

    self._model = UnnormalizedLogLinearModel(feature_function, weight_list)

    # TODO(crbug.com/674262): remove the need for storing these weights.
    self._weights = weights

  # TODO(crbug.com/673964): something better for detecting "close to log(0)".
  def _LogZeroish(self, x):
    """Determine whether a float is close enough to log(0).

    If a ``FeatureValue`` has a (log-domain) score of -inf for a given
    ``Suspect``, then that suspect has zero probability of being the
    culprit. We want to filter these suspects out, to clean up the
    output of classification; so this method encapsulates the logic of
    that check.

    Args:
      x (float): the float to check

    Returns:
      ``True`` if ``x`` is close enough to log(0); else ``False``.
    """
    return x < 0 and math.isinf(x)

  def _SingleFeatureScore(self, feature_value):
    """Returns the score (aka weighted value) of a ``FeatureValue``.

    This method is a hack for filtering the JSON output ``__call__``
    returns. If we really really need this, then we should probably move
    it to the classes defining loglinear models.

    Args:
      feature_value (FeatureValue): the feature value to check.

    Returns:
      The score of the feature value.
    """
    return feature_value.value * self._weights.get(feature_value.name, 0.)

  def __call__(self, report):
    """Finds changelists suspected of being responsible for the crash report.

    Args:
      report (CrashReport): the report to be analyzed.

    Returns:
      List of ``Suspect``s, sorted by probability from highest to lowest.
    """
    if not report.regression_range:
      logging.warning('ChangelistClassifier.__call__: Missing regression range '
          'for report: %s', str(report))
      return []
    last_good_version, first_bad_version = report.regression_range
    logging.info('ChangelistClassifier.__call__: Regression range %s:%s',
        last_good_version, first_bad_version)

    # Restrict analysis to just the top n frames in each callstack.
    stacktrace = Stacktrace([
        stack.SliceFrames(None, self._top_n_frames)
        for stack in report.stacktrace])

    # We are only interested in the deps in crash stack (the callstack that
    # caused the crash).
    # TODO(wrengr): we may want to receive the crash deps as an argument,
    # so that when this method is called via Findit.FindCulprit, we avoid
    # doing redundant work creating it.
    stack_deps = changelist_classifier.GetDepsInCrashStack(
        report.stacktrace.crash_stack,
        chrome_dependency_fetcher.ChromeDependencyFetcher(
            self._repository).GetDependency(report.crashed_version,
                                            report.platform))

    # Get dep and file to changelogs, stack_info and blame dicts.
    dep_rolls = chrome_dependency_fetcher.ChromeDependencyFetcher(
        self._repository).GetDependencyRollsDict(
            last_good_version, first_bad_version, report.platform)

    # Regression of a dep added/deleted (old_revision/new_revision is None) can
    # not be known for sure and this case rarely happens, so just filter them
    # out.
    regression_deps_rolls = {}
    for dep_path, dep_roll in dep_rolls.iteritems():
      if not dep_roll.old_revision or not dep_roll.new_revision:
        logging.info('Skip %s denpendency %s',
                     'added' if dep_roll.new_revision else 'deleted', dep_path)
        continue
      regression_deps_rolls[dep_path] = dep_roll

    dep_to_file_to_changelogs, ignore_cls = (
        changelist_classifier.GetChangeLogsForFilesGroupedByDeps(
            regression_deps_rolls, stack_deps, self._repository))
    dep_to_file_to_stack_infos = (
        changelist_classifier.GetStackInfosForFilesGroupedByDeps(
            stacktrace, stack_deps))

    # Get the possible suspects.
    suspects = changelist_classifier.FindSuspects(
        dep_to_file_to_changelogs,
        dep_to_file_to_stack_infos,
        stack_deps,
        self._repository,
        ignore_cls)
    if suspects is None:
      return []

    # Score the suspects and organize them for outputting/returning.
    features_given_report = self._model.Features(report)
    score_given_report = self._model.Score(report)
    scored_suspects = []
    for suspect in suspects:
      score = score_given_report(suspect)
      if self._LogZeroish(score):
        logging.debug('Discarding suspect because it has zero probability: %s'
            % str(suspect.ToDict()))
        continue

      suspect.confidence = score
      features = features_given_report(suspect)
      suspect.reasons = self.FormatReasons(features)
      suspect.changed_files = [changed_file.ToDict()
          for changed_file in self.AggregateChangedFiles(features)]
      scored_suspects.append(suspect)

    scored_suspects.sort(key=lambda suspect: suspect.confidence)
    return scored_suspects[:self._top_n_suspects]

  def FormatReasons(self, features):
    """Collect and format a list of all ``FeatureValue.reason`` strings.

    Args:
      features (list of FeatureValue): the values whose ``reason``
        strings should be collected.

    Returns:
      A list of ``(str, float, str)`` triples; where the first string is
      the feature name, the float is some numeric representation of how
      much influence this feature exerts on the ``Suspect`` being blamed,
      and the final string is the ``FeatureValue.reason``. The list is
      sorted by feature name, just to ensure that it comes out in some
      canonical order.

      At present, the float is the log-domain score of the feature
      value. However, this isn't the best thing for UX reasons. In the
      future it might be replaced by the normal-domain score, or by
      the probability.
    """
    formatted_reasons = []
    for feature in features:
      feature_score = self._SingleFeatureScore(feature)
      if self._LogZeroish(feature_score): # pragma: no cover
        logging.debug('Discarding reasons from feature %s'
            ' because it has zero probability' % feature.name)
        continue

      formatted_reasons.append((feature.name, feature_score, feature.reason))

    return sorted(formatted_reasons,
        key=lambda formatted_reason: formatted_reason[0])

  def AggregateChangedFiles(self, features):
    """Merge multiple``FeatureValue.changed_files`` lists into one.

    Args:
      features (list of FeatureValue): the values whose ``changed_files``
        lists should be aggregated.

    Returns:
      A list of ``ChangedFile`` objects sorted by file name. The sorting
      is not essential, but is provided to ease testing by ensuring the
      output is in some canonical order.

    Raises:
      ``ValueError`` if any file name is given inconsistent ``blame_url``s.
    """
    all_changed_files = {}
    for feature in features:
      if self._LogZeroish(self._SingleFeatureScore(feature)): # pragma: no cover
        logging.debug('Discarding changed files from feature %s'
            ' because it has zero probability' % feature.name)
        continue

      for changed_file in feature.changed_files or []:
        accumulated_changed_file = all_changed_files.get(changed_file.name)
        if accumulated_changed_file is None:
          all_changed_files[changed_file.name] = changed_file
          continue

        assert accumulated_changed_file.blame_url == changed_file.blame_url, (
            ValueError('Blame URLs do not match: %s != %s'
                % (accumulated_changed_file.blame_url, changed_file.blame_url)))
        accumulated_changed_file.reasons.extend(changed_file.reasons or [])

    return sorted(all_changed_files.values(),
        key=lambda changed_file: changed_file.name)
