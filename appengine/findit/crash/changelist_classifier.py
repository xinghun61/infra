# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from collections import defaultdict
from collections import namedtuple

from common.chrome_dependency_fetcher import ChromeDependencyFetcher
from crash import crash_util
from crash.suspect import StackInfo
from crash.suspect import Suspect
from crash.suspect import SuspectMap
from crash.scorers.aggregated_scorer import AggregatedScorer
from crash.scorers.min_distance import MinDistance
from crash.scorers.top_frame_index import TopFrameIndex
from crash.stacktrace import CallStack
from crash.stacktrace import Stacktrace
from libs.gitiles.diff import ChangeType


class ChangelistClassifier(namedtuple('ChangelistClassifier',
    ['get_repository', 'top_n_results', 'confidence_threshold'])):
  __slots__ = ()

  def __new__(cls, get_repository, top_n_results=3, confidence_threshold=0.999):
    """Args:
      get_repository (callable): a function from DEP urls to ``Repository``
        objects, so we can get changelogs and blame for each dep. Notably,
        to keep the code here generic, we make no assumptions about
        which subclass of ``Repository`` this function returns. Thus,
        it is up to the caller to decide what class to return and handle
        any other arguments that class may require (e.g., an http client
        for ``GitilesRepository``).
      top_n_results (int): maximum number of results to return.
      confidence_threshold (float): In [0,1], above which we only return
        the first suspect.
    """
    return super(cls, ChangelistClassifier).__new__(
        cls, get_repository, top_n_results, confidence_threshold)

  def __str__(self): # pragma: no cover
    return ('%s(top_n_results=%d, confidence_threshold=%g)'
        % (self.__class__.__name__,
           self.top_n_results,
           self.confidence_threshold))

  def __call__(self, report):
    """Finds changelists suspected of being responsible for the crash report.

    This function assumes the report's stacktrace has already had any necessary
    preprocessing (like filtering or truncating) applied.

    Args:
      report (CrashReport): the report to be analyzed.

    Returns:
      List of ``Suspect``s, sorted by confidence from highest to lowest.
    """
    if not report.regression_range:
      logging.warning('ChangelistClassifier.__call__: Missing regression range '
          'for report: %s', str(report))
      return []
    last_good_version, first_bad_version = report.regression_range
    logging.info('ChangelistClassifier.__call__: Regression range %s:%s',
        last_good_version, first_bad_version)

    dependency_fetcher = ChromeDependencyFetcher(self.get_repository)

    # We are only interested in the deps in crash stack (the callstack that
    # caused the crash).
    # TODO(wrengr): we may want to receive the crash deps as an argument,
    # so that when this method is called via Findit.FindCulprit, we avoid
    # doing redundant work creating it.
    stack_deps = GetDepsInCrashStack(
        report.stacktrace.crash_stack,
        dependency_fetcher.GetDependency(
            report.crashed_version, report.platform))

    # Get dep and file to changelogs, stack_info and blame dicts.
    dep_rolls = dependency_fetcher.GetDependencyRollsDict(
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
        regression_deps_rolls, stack_deps, self.get_repository)
    dep_to_file_to_stack_infos = GetStackInfosForFilesGroupedByDeps(
        report.stacktrace, stack_deps)

    suspects = FindSuspects(dep_to_file_to_changelogs,
                            dep_to_file_to_stack_infos,
                            stack_deps, self.get_repository, ignore_cls)
    if not suspects:
      return []

    # Set confidence, reasons, and changed_files.
    aggregated_scorer = AggregatedScorer([TopFrameIndex(), MinDistance()])
    map(aggregated_scorer.Score, suspects)

    # Filter all the 0 confidence results.
    suspects = filter(lambda suspect: suspect.confidence != 0, suspects)
    if not suspects:
      return []

    suspects.sort(key=lambda suspect: -suspect.confidence)

    max_results = (1 if suspects[0].confidence > self.confidence_threshold
      else self.top_n_results)

    return suspects[:max_results]


def GetDepsInCrashStack(crash_stack, crash_deps):
  """Gets Dependencies in crash stack."""
  if not crash_stack:
    return {}

  stack_deps = {}
  for frame in crash_stack.frames:
    if frame.dep_path:
      stack_deps[frame.dep_path] = crash_deps[frame.dep_path]

  return stack_deps


# TODO(katesonia): Remove the repository argument after refatoring cl committed.
def GetChangeLogsForFilesGroupedByDeps(regression_deps_rolls, stack_deps,
                                       get_repository):
  """Gets a dict containing files touched by changelogs for deps in stack_deps.

  Regression ranges for each dep is determined by regression_deps_rolls.
  Changelogs which were reverted are returned in a reverted_cls set.

  Args:
    regression_deps_rolls (dict): Maps dep_path to DependencyRoll in
      regression range.
    stack_deps (dict): Represents all the dependencies shown in
      the crash stack.
    get_repository (callable): a function from DEP urls to ``Repository``
      objects, so we can get changelogs and blame for each dep. Notably,
      to keep the code here generic, we make no assumptions about
      which subclass of ``Repository`` this function returns. Thus,
      it is up to the caller to decide what class to return and handle
      any other arguments that class may require (e.g., an http client
      for ``GitilesRepository``).

  Returns:
    A tuple (dep_to_file_to_changelogs, reverted_cls).

    dep_to_file_to_changelogs (dict): Maps dep_path to a dict mapping file path
      to ChangeLogs that touched this file.
    For example:
    {
        'src/': {
            'a.cc': [
                ChangeLog.FromDict({
                    'author': {
                        'name': 'test@chromium.org',
                        'email': 'example@chromium.org',
                        'time': 'Thu Mar 31 21:24:43 2016',
                    },
                    'committer': {
                        'name': 'example@chromium.org',
                        'email': 'example@chromium.org',
                        'time': 'Thu Mar 31 21:28:39 2016',
                    },
                    'message': 'dummy',
                    'commit_position': 175976,
                    'touched_files': [
                        {
                            'change_type': 'add',
                            'new_path': 'a.cc',
                            'old_path': 'b/a.cc'
                        },
                        ...
                    ],
                    'commit_url':
                        'https://repo.test/+/bcfd',
                    'code_review_url': 'https://codereview.chromium.org/3281',
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

    repository = get_repository(dep_roll.repo_url)
    changelogs = repository.GetChangeLogs(dep_roll.old_revision,
                                          dep_roll.new_revision)

    for changelog in changelogs or []:
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
                StackInfo(StackFrame(0, 'src/', '', 'func', 'a.cc', [1]), 0),
                StackInfo(StackFrame(2, 'src/', '', 'func', 'a.cc', [33]), 0),
            ]
        }
    }
  """
  dep_to_file_to_stack_infos = defaultdict(lambda: defaultdict(list))

  for callstack in stacktrace.stacks:
    for frame in callstack.frames:
      # We only care about those dependencies in crash stack.
      if frame.dep_path not in stack_deps:
        continue

      dep_to_file_to_stack_infos[frame.dep_path][frame.file_path].append(
          StackInfo(frame, callstack.priority))

  return dep_to_file_to_stack_infos


# TODO(katesonia): Remove the repository argument after refatoring cl committed.
def FindSuspects(dep_to_file_to_changelogs,
                 dep_to_file_to_stack_infos,
                 stack_deps, get_repository,
                 ignore_cls=None):
  """Finds suspects by matching stacktrace and changelogs in regression range.

  This method only applies to those crashes with regression range.

  Args:
    dep_to_file_to_changelogs (dict): Maps dep_path to a dict mapping file path
      to ChangeLogs that touched this file.
    dep_to_file_to_stack_infos (dict): Maps dep path to a dict mapping file path
      to a list of stack information of this file. A file may occur in several
      frames, one stack info consist of a StackFrame and the callstack priority
      of it.
    stack_deps (dict): Represents all the dependencies shown in the crash stack.
    get_repository (callable): a function from urls to ``Repository``
      objects, so we can get changelogs and blame for each dep.
    ignore_cls (set): Set of reverted revisions.

  Returns:
    A list of ``Suspect`` instances with confidence and reason unset.
  """
  suspects = SuspectMap(ignore_cls)

  for dep, file_to_stack_infos in dep_to_file_to_stack_infos.iteritems():
    file_to_changelogs = dep_to_file_to_changelogs[dep]

    for crashed_file_path, stack_infos in file_to_stack_infos.iteritems():
      for touched_file_path, changelogs in file_to_changelogs.iteritems():
        if not crash_util.IsSameFilePath(crashed_file_path, touched_file_path):
          continue

        repository = get_repository(stack_deps[dep].repo_url)
        blame = repository.GetBlame(touched_file_path,
                                    stack_deps[dep].revision)

        # Generate/update each suspect(changelog) in changelogs, blame is used
        # to calculate distance between touched lines and crashed lines in file.
        suspects.GenerateSuspects(
            touched_file_path, dep, stack_infos, changelogs, blame)

  return suspects.values()
