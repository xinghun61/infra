# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import logging

from common.chrome_dependency_fetcher import ChromeDependencyFetcher
from crash import changelist_classifier
from crash.changelist_classifier import StackInfo
from crash.crash_report import CrashReport
from crash.loglinear.model import UnnormalizedLogLinearModel


class LogLinearChangelistClassifier(object):
  """A ``LogLinearModel``-based implementation of CL classification."""

  def __init__(self, get_repository, meta_feature, meta_weight,
               top_n_frames=7, top_n_suspects=3):
    """
    Args:
      get_repository (callable): a function from DEP urls to ``Repository``
        objects, so we can get changelogs and blame for each dep. Notably,
        to keep the code here generic, we make no assumptions about
        which subclass of ``Repository`` this function returns. Thus,
        it is up to the caller to decide what class to return and handle
        any other arguments that class may require (e.g., an http client
        for ``GitilesRepository``).
      meta_feature (MetaFeature): All features.
      meta_weight (MetaWeight): All weights. the weights for the features.
        The keys of the dictionary are the names of the feature that weight is
        for. We take this argument as a dict rather than as a list so that
        callers needn't worry about what order to provide the weights in.
      top_n_frames (int): how many frames of each callstack to look at.
      top_n_suspects (int): maximum number of suspects to return.
    """
    self._dependency_fetcher = ChromeDependencyFetcher(get_repository)
    self._get_repository = get_repository
    self._top_n_frames = top_n_frames
    self._top_n_suspects = top_n_suspects
    self._model = UnnormalizedLogLinearModel(meta_feature, meta_weight)

  def __call__(self, report):
    """Finds changelists suspected of being responsible for the crash report.

    Args:
      report (CrashReport): the report to be analyzed.

    Returns:
      List of ``Suspect``s, sorted by probability from highest to lowest.
    """
    suspects = self.GenerateSuspects(report)
    if not suspects:
      logging.warning('%s.__call__: Found no suspects for report: %s',
          self.__class__.__name__, str(report))
      return []

    return self.RankSuspects(report, suspects)

  def GenerateSuspects(self, report):
    """Generate all possible suspects for the reported crash.

    Args:
      report (CrashReport): the crash we seek to explain.

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

    Suspects with a discardable score or lower ranking than top_n_suspects
    will be filtered.

    Args:
      report (CrashReport): the crash we seek to explain.
      suspects (iterable of Suspect): the CLs to consider blaming for the crash.

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
      if self._model.LogZeroish(score):
        logging.debug('Discarding suspect because it has zero probability: %s'
            % str(suspect.ToDict()))
        continue

      suspect.confidence = score
      # features is ``MetaFeatureValue`` object containing all feature values.
      features = features_given_report(suspect)
      suspect.reasons = features.reason
      suspect.changed_files = [changed_file.ToDict()
                               for changed_file in features.changed_files]
      scored_suspects.append(suspect)

    scored_suspects.sort(key=lambda suspect: suspect.confidence)
    return scored_suspects[:self._top_n_suspects]
