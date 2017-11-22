# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from analysis import log_util
from analysis.linear.model import UnnormalizedLogLinearModel
from analysis.suspect import Suspect
from analysis.suspect_filters import FilterIgnoredRevisions
from analysis.suspect_filters import FilterLessLikelySuspects
from analysis.suspect_filters import FilterSuspectFromRobotAuthor
from analysis.type_enums import LogLevel

# The ratio of the probabilities of 2 suspects.
_PROBABILITY_RATIO = 0.5
_ABSOLUTE_CONFIDENCE_SCORE = 50


class ChangelistClassifier(object):
  """A ``LogLinearModel``-based implementation of CL classification."""

  def __init__(self, get_repository, meta_feature, meta_weight):
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
    """
    self._get_repository = get_repository
    self._model = UnnormalizedLogLinearModel(meta_feature, meta_weight)
    # Filters that apply to suspects before computing features and ranking
    # scores.
    self._before_ranking_filters = [FilterIgnoredRevisions(get_repository),
                                    FilterSuspectFromRobotAuthor()]
    # Filters that apply to suspects after computing features and ranking
    # scores, which need to use information got from features like
    # ``confidence``.
    self._after_ranking_filters = [FilterLessLikelySuspects(_PROBABILITY_RATIO)]
    self._log = None

  def __call__(self, report):
    """Finds changelists suspected of being responsible for the crash report.

    Args:
      report (CrashReport): the report to be analyzed.
      log (Log): log information we want to send back to clients.

    Returns:
      List of ``Suspect``s, sorted by probability from highest to lowest.
    """
    if not report.regression_range:
      log_util.Log(
          self._log, 'NoRegressionRange',
          'Can\'t find culprits due to unavailable regression range.',
          LogLevel.WARNING)
      return []

    suspects = self.GenerateSuspects(report)
    if not suspects:
      logging.warning('%s.__call__: Found no suspects for report: %s',
          self.__class__.__name__, str(report))
      return []

    if len(suspects) == 1:
      suspect = suspects[0]
      suspect.confidence = _ABSOLUTE_CONFIDENCE_SCORE
      suspect.reasons = [
          'The suspect is the only commit in the regression range.']
      return [suspect]

    if not report.stacktrace:
      log_util.Log(
          self._log, 'FailedToParseStacktrace',
          'Can\'t find culprits because Predator failed to parse stacktrace.',
          LogLevel.ERROR)
      return []

    return self.FindSuspects(report, suspects)

  def SetLog(self, log):
    self._log = log

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
    reverted_revisions = []
    revision_to_suspects = {}
    for dep_roll in report.dependency_rolls.itervalues():
      repository = self._get_repository(dep_roll.repo_url)
      changelogs = repository.GetChangeLogs(dep_roll.old_revision,
                                            dep_roll.new_revision)

      for changelog in changelogs or []:
        # When someone reverts, we need to skip both the CL doing
        # the reverting as well as the CL that got reverted. If
        # ``reverted_revision`` is true, then this CL reverts another one,
        # so we skip it and save the CL it reverts in ``reverted_cls`` to
        # be filtered out later.
        if changelog.reverted_revision:
          reverted_revisions.append(changelog.reverted_revision)
          continue

        revision_to_suspects[changelog.revision] = Suspect(changelog,
                                                           dep_roll.path)

    for reverted_revision in reverted_revisions:
      if reverted_revision in revision_to_suspects:
        del revision_to_suspects[reverted_revision]

    return revision_to_suspects.values()

  def RankSuspects(self, report, suspects):
    """Returns a lineup of the suspects in order of likelihood.

    Computes features, so as to get confidence and reasons for each suspect and
    returns a sorted list of suspects ranked by likelihood.

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
      suspect.reasons = self._model.FilterReasonWithWeight(features.reason)
      suspect.changed_files = [changed_file.ToDict()
                               for changed_file in features.changed_files]
      scored_suspects.append(suspect)

    scored_suspects.sort(key=lambda suspect: -suspect.confidence)
    return scored_suspects

  @staticmethod
  def _FilterSuspects(suspects, suspect_filters):
    """Filters suspects using ``suspect_filters``."""
    if not suspects or len(suspects) == 1 or not suspect_filters:
      return suspects

    for suspect_filter in suspect_filters:
      suspects = suspect_filter(suspects)

    return suspects

  def FindSuspects(self, report, suspects):
    """Finds a list of ``Suspect``s for potential suspects."""
    suspects = self._FilterSuspects(suspects, self._before_ranking_filters)
    suspects = self.RankSuspects(report, suspects)
    return self._FilterSuspects(suspects, self._after_ranking_filters)
