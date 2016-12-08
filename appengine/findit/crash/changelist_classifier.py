# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from collections import defaultdict
from collections import namedtuple

from common import chrome_dependency_fetcher
from crash import crash_util
from crash.results import MatchResults
from crash.scorers.aggregated_scorer import AggregatedScorer
from crash.scorers.min_distance import MinDistance
from crash.scorers.top_frame_index import TopFrameIndex
from crash.stacktrace import CallStack
from crash.stacktrace import Stacktrace
from libs.gitiles.diff import ChangeType


class ChangelistClassifier(namedtuple('ChangelistClassifier',
    ['repository', 'top_n_frames', 'top_n_results', 'confidence_threshold'])):
  __slots__ = ()

  def __new__(cls, repository,
      top_n_frames, top_n_results=3, confidence_threshold=0.999):
    """Args:
      repository (Repository): the Git repository for getting CLs to classify.
      top_n_frames (int): how many frames of each callstack to look at.
      top_n_results (int): maximum number of results to return.
      confidence_threshold (float): In [0,1], above which we only return
        the first result.
    """
    return super(cls, ChangelistClassifier).__new__(cls,
        repository, top_n_frames, top_n_results, confidence_threshold)

  def __str__(self): # pragma: no cover
    return ('%s(top_n_frames=%d, top_n_results=%d, confidence_threshold=%g)'
        % (self.__class__.__name__,
           self.top_n_frames,
           self.top_n_results,
           self.confidence_threshold))

  def __call__(self, report):
    """Finds changelists suspected of being responsible for the crash report.

    Args:
      report (CrashReport): the report to be analyzed.

    Returns:
      List of Results, sorted by confidence from highest to lowest.
    """
    if not report.regression_range:
      logging.warning('ChangelistClassifier.__call__: Missing regression range '
          'for report: %s', str(report))
      return []
    last_good_version, first_bad_version = report.regression_range
    logging.info('ChangelistClassifier.__call__: Regression range %s:%s',
        last_good_version, first_bad_version)

    # Restrict analysis to just the top n frames in each callstack.
    # TODO(wrengr): move this to be a Stacktrace method?
    stacktrace = Stacktrace([
        CallStack(stack.priority,
                  format_type=stack.format_type,
                  language_type=stack.language_type,
                  frame_list=stack[:self.top_n_frames])
        for stack in report.stacktrace])

    # We are only interested in the deps in crash stack (the callstack that
    # caused the crash).
    # TODO(wrengr): we may want to receive the crash deps as an argument,
    # so that when this method is called via Findit.FindCulprit, we avoid
    # doing redundant work creating it.
    stack_deps = GetDepsInCrashStack(
        report.stacktrace.crash_stack,
        chrome_dependency_fetcher.ChromeDependencyFetcher(
            self.repository).GetDependency(report.crashed_version,
                                           report.platform))

    # Get dep and file to changelogs, stack_info and blame dicts.
    dep_rolls = chrome_dependency_fetcher.ChromeDependencyFetcher(
        self.repository).GetDependencyRollsDict(
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

    dep_to_file_to_changelogs, ignore_cls = GetChangeLogsForFilesGroupedByDeps(
        regression_deps_rolls, stack_deps, self.repository)
    dep_to_file_to_stack_infos = GetStackInfosForFilesGroupedByDeps(
        stacktrace, stack_deps)

    # TODO: argument order is inconsistent from others. Repository should
    # be last argument.
    results = FindMatchResults(dep_to_file_to_changelogs,
                               dep_to_file_to_stack_infos,
                               stack_deps, self.repository, ignore_cls)
    if not results:
      return []

    # TODO(wrengr): we should be able to do this map/filter/sort in one pass.
    # Set result.confidence, result.reasons and result.changed_files.
    aggregated_scorer = AggregatedScorer([TopFrameIndex(), MinDistance()])
    map(aggregated_scorer.Score, results)

    # Filter all the 0 confidence results.
    results = filter(lambda r: r.confidence != 0, results)
    if not results:
      return []

    sorted_results = sorted(results, key=lambda r: -r.confidence)

    max_results = (1 if sorted_results[0].confidence > self.confidence_threshold
      else self.top_n_results)

    return sorted_results[:max_results]


def GetDepsInCrashStack(crash_stack, crash_deps):
  """Gets Dependencies in crash stack."""
  if not crash_stack:
    return {}

  stack_deps = {}
  for frame in crash_stack:
    if frame.dep_path:
      stack_deps[frame.dep_path] = crash_deps[frame.dep_path]

  return stack_deps


# TODO(katesonia): Remove the repository argument after refatoring cl committed.
def GetChangeLogsForFilesGroupedByDeps(regression_deps_rolls, stack_deps,
                                       repository):
  """Gets a dict containing files touched by changelogs for deps in stack_deps.

  Regression ranges for each dep is determined by regression_deps_rolls.
  Changelogs which were reverted are returned in a reverted_cls set.

  Args:
    regression_deps_rolls (dict): Maps dep_path to DependencyRoll in
      regression range.
    stack_deps (dict): Represents all the dependencies shown in
      the crash stack.
    repository (Repository): Repository to get changelogs from.

  Returns:
    A tuple (dep_to_file_to_changelogs, reverted_cls).

    dep_to_file_to_changelogs (dict): Maps dep_path to a dict mapping file path
      to ChangeLogs that touched this file.
    For example:
    {
        'src/': {
            'a.cc': [
                ChangeLog.FromDict({
                    'author_name': 'test@chromium.org',
                    'message': 'dummy',
                    'committer_email': 'example@chromium.org',
                    'commit_position': 175976,
                    'author_email': 'example@chromium.org',
                    'touched_files': [
                        {
                            'change_type': 'add',
                            'new_path': 'a.cc',
                            'old_path': 'b/a.cc'
                        },
                        ...
                    ],
                    'author_time': 'Thu Mar 31 21:24:43 2016',
                    'committer_time': 'Thu Mar 31 21:28:39 2016',
                    'commit_url':
                        'https://repo.test/+/bcfd',
                    'code_review_url': 'https://codereview.chromium.org/3281',
                    'committer_name': 'example@chromium.org',
                    'revision': 'bcfd',
                    'reverted_revision': None
                }),
            ]
        }
    }

    reverted_cls (set): A set of reverted revisions.
  """
  dep_to_file_to_changelogs = defaultdict(lambda: defaultdict(list))
  reverted_cls = set()

  for dep in stack_deps:
    # If a dep is not in regression range, than it cannot be the dep of
    # culprits.
    dep_roll = regression_deps_rolls.get(dep)
    if not dep_roll:
      continue

    dep_roll = regression_deps_rolls[dep]

    repository.repo_url = dep_roll.repo_url
    changelogs = repository.GetChangeLogs(dep_roll.old_revision,
                                          dep_roll.new_revision)

    if not changelogs:
      continue

    for changelog in changelogs:
      # When someone reverts, we need to skip both the CL doing
      # the reverting as well as the CL that got reverted. If
      # ``reverted_revision`` is true, then this CL reverts another one,
      # so we skip it and save the CL it reverts in ``reverted_cls`` to
      # be filtered out later.
      if changelog.reverted_revision:
        reverted_cls.add(changelog.reverted_revision)
        continue

      for touched_file in changelog.touched_files:
        if touched_file.change_type == ChangeType.DELETE:
          continue

        dep_to_file_to_changelogs[dep][touched_file.new_path].append(changelog)

  return dep_to_file_to_changelogs, reverted_cls


def GetStackInfosForFilesGroupedByDeps(stacktrace, stack_deps):
  """Gets a dict containing all the stack information of files in stacktrace.

  Only gets stack informations for files grouped by deps in stack_deps.

  Args:
    stacktrace (Stacktrace): Parsed stacktrace object.
    stack_deps (dict): Represents all the dependencies show in
      the crash stack.

  Returns:
    A dict, maps dep path to a dict mapping file path to a list of stack
    information of this file. A file may occur in several frames, one
    stack info consist of a StackFrame and the callstack priority of it.

    For example:
    {
        'src/': {
            'a.cc': [
                (StackFrame(0, 'src/', '', 'func', 'a.cc', [1]), 0),
                (StackFrame(2, 'src/', '', 'func', 'a.cc', [33]), 0),
            ]
        }
    }
  """
  dep_to_file_to_stack_infos = defaultdict(lambda: defaultdict(list))

  for callstack in stacktrace:
    for frame in callstack:
      # We only care about those dependencies in crash stack.
      if frame.dep_path not in stack_deps:
        continue

      dep_to_file_to_stack_infos[frame.dep_path][frame.file_path].append((
          frame, callstack.priority))

  return dep_to_file_to_stack_infos


# TODO(katesonia): Remove the repository argument after refatoring cl committed.
def FindMatchResults(dep_to_file_to_changelogs,
                     dep_to_file_to_stack_infos,
                     stack_deps, repository,
                     ignore_cls=None):
  """Finds results by matching stacktrace and changelogs in regression range.

  This method only applies to those crashes with regression range.

  Args:
    dep_to_file_to_changelogs (dict): Maps dep_path to a dict mapping file path
      to ChangeLogs that touched this file.
    dep_to_file_to_stack_infos (dict): Maps dep path to a dict mapping file path
      to a list of stack information of this file. A file may occur in several
      frames, one stack info consist of a StackFrame and the callstack priority
      of it.
    stack_deps (dict): Represents all the dependencies shown in the crash stack.
    repository (Repository): Repository to get changelogs and blame from.
    ignore_cls (set): Set of reverted revisions.

  Returns:
    A list of MatchResult instances with confidence and reason unset.
  """
  match_results = MatchResults(ignore_cls)

  for dep, file_to_stack_infos in dep_to_file_to_stack_infos.iteritems():
    file_to_changelogs = dep_to_file_to_changelogs[dep]

    for crashed_file_path, stack_infos in file_to_stack_infos.iteritems():
      for touched_file_path, changelogs in file_to_changelogs.iteritems():
        if not crash_util.IsSameFilePath(crashed_file_path, touched_file_path):
          continue

        repository.repo_url = stack_deps[dep].repo_url
        blame = repository.GetBlame(touched_file_path,
                                    stack_deps[dep].revision)

        # Generate/update each result(changelog) in changelogs, blame is used
        # to calculate distance between touched lines and crashed lines in file.
        match_results.GenerateMatchResults(
            touched_file_path, dep, stack_infos, changelogs, blame)

  return match_results.values()
