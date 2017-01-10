# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import logging
import math

from common.chrome_dependency_fetcher import ChromeDependencyFetcher
from crash import changelist_classifier
from crash.crash_report_with_dependencies import CrashReportWithDependencies
from crash.loglinear.changelist_features import min_distance
from crash.loglinear.changelist_features import top_frame_index
from crash.loglinear.model import ToFeatureFunction
from crash.loglinear.model import UnnormalizedLogLinearModel
from crash.stacktrace import CallStack
from crash.stacktrace import Stacktrace
from crash.suspect import StackInfo


class LogLinearChangelistClassifier(object):
  """A ``LogLinearModel``-based implementation of CL classification."""

  def __init__(self, get_repository, weights, top_n_frames=7, top_n_suspects=3):
    """Args:
      get_repository (callable): a function from DEP urls to ``Repository``
        objects, so we can get changelogs and blame for each dep. Notably,
        to keep the code here generic, we make no assumptions about
        which subclass of ``Repository`` this function returns. Thus,
        it is up to the caller to decide what class to return and handle
        any other arguments that class may require (e.g., an http client
        for ``GitilesRepository``).
      weights (dict of float): the weights for the features. The keys of
        the dictionary are the names of the feature that weight is
        for. We take this argument as a dict rather than as a list so that
        callers needn't worry about what order to provide the weights in.
      top_n_frames (int): how many frames of each callstack to look at.
      top_n_suspects (int): maximum number of suspects to return.
    """
    self._dependency_fetcher = ChromeDependencyFetcher(get_repository)
    self._get_repository = get_repository
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

    This function assumes the report's stacktrace has already had any necessary
    preprocessing (like filtering or truncating) applied.

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
    annotated_report = CrashReportWithDependencies(
        report, self._dependency_fetcher)
    if annotated_report is None:
      logging.warning('%s.__call__: '
          'Could not obtain dependencies for report: %s',
          self.__class__.__name__, str(report))
      return []

    suspects = self.GenerateSuspects(annotated_report)
    if not suspects:
      logging.warning('%s.__call__: Found no suspects for report: %s',
          self.__class__.__name__, str(annotated_report))
      return []

    return self.RankSuspects(annotated_report, suspects)

  def GenerateSuspects(self, report):
    """Generate all possible suspects for the reported crash.

    Args:
      report (CrashReportWithDependencies): the crash we seek to explain.

    Returns:
      A list of ``Suspect``s who may be to blame for the
      ``report``. Notably these ``Suspect`` instances do not have
      all their fields filled in. They will be filled in later by
      ``RankSuspects``.
    """
    # Look at all the frames from any stack in the crash report, and
    # organize the ones that come from dependencies we care about.
    dep_to_file_to_stack_infos = defaultdict(lambda: defaultdict(list))
    for stack in report.stacktrace:
      for frame in stack:
        if frame.dep_path in report.dependencies:
          dep_to_file_to_stack_infos[frame.dep_path][frame.file_path].append(
              StackInfo(frame, stack.priority))

    dep_to_file_to_changelogs, ignore_cls = (
        changelist_classifier.GetChangeLogsForFilesGroupedByDeps(
            report.dependency_rolls, report.dependencies,
            self._get_repository))

    # Get the possible suspects.
    return changelist_classifier.FindSuspects(
        dep_to_file_to_changelogs,
        dep_to_file_to_stack_infos,
        report.dependencies,
        self._get_repository,
        ignore_cls)

  def RankSuspects(self, report, suspects):
    """Returns a lineup of the suspects in order of likelihood.

    Args:
      report (CrashReportWithDependencies): the crash we seek to explain.
      suspects (list of Suspect): the CLs to consider blaming for the crash.

    Returns:
      A list of suspects in order according to their likelihood. This
      list contains elements of the ``suspects`` list, where we mutate
      some of the fields to store information about why that suspect
      is being blamed (e.g., the ``confidence``, ``reasons``, and
      ``changed_files`` fields are updated). In addition to sorting the
      suspects, we also filter out those which are exceedingly unlikely
      or don't make the ``top_n_suspects`` cut.
    """
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
      suspect.changed_files = [
          changed_file.ToDict()
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

        if (accumulated_changed_file.blame_url !=
            changed_file.blame_url): # pragma: no cover
          raise ValueError('Blame URLs do not match: %s != %s'
              % (accumulated_changed_file.blame_url, changed_file.blame_url))
        accumulated_changed_file.reasons.extend(changed_file.reasons or [])

    return sorted(all_changed_files.values(),
        key=lambda changed_file: changed_file.name)
