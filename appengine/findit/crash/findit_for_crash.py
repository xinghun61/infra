# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from common.diff import ChangeType
from common.git_repository import GitRepository
from common.http_client_appengine import HttpClientAppengine
from crash import crash_util
from crash.results import MatchResults
from crash.scorers.aggregator import Aggregator
from crash.scorers.min_distance import MinDistance
from crash.scorers.top_frame_index import TopFrameIndex


def GetDepsInCrashStack(crash_stack, crash_deps):
  """Gets Dependencies in crash stack."""
  if not crash_stack:
    return {}

  stack_deps = {}
  for frame in crash_stack:
    stack_deps[frame.dep_path] = crash_deps[frame.dep_path]

  return stack_deps


def GetChangeLogsForFilesGroupedByDeps(regression_deps_rolls, stack_deps):
  """Gets a dict containing files touched by changelogs for deps in stack_deps.

  Regression ranges for each dep is determined by regression_deps_rolls.
  Those changelogs got reverted should be returned in a ignore_cls set.

  Args:
    regression_deps_rolls (dict): Maps dep_path to DependencyRoll in
      regression range.
    stack_deps (dict): Represents all the dependencies shown in
      the crash stack.

  Returns:
    A tuple (dep_to_file_to_changelogs, ignore_cls).

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

    ignore_cls (set): A set of reverted revisions.
  """
  dep_to_file_to_changelogs = defaultdict(lambda: defaultdict(list))
  ignore_cls = set()

  for dep in stack_deps:
    dep_roll = regression_deps_rolls[dep]

    git_repository = GitRepository(dep_roll['repo_url'], HttpClientAppengine())
    changelogs = git_repository.GetChangeLogs(dep_roll['old_revision'],
                                              dep_roll['new_revision'])

    for changelog in changelogs:
      if changelog.reverted_revision:
        # Skip reverting cls and add reverted revisions to ignore_cls to later
        # filter those reverted revisions.
        ignore_cls.add(changelog.reverted_revision)
        continue

      for touched_file in changelog.touched_files:
        if touched_file.change_type == ChangeType.DELETE:
          continue

        dep_to_file_to_changelogs[dep][touched_file.new_path].append(changelog)

  return dep_to_file_to_changelogs, ignore_cls


def GetStackInfosForFilesGroupedByDeps(stacktrace, stack_deps):
  """Gets a dict containing all the stack information of files in stacktrace.

  Only gets stack informations for files grouped by deps in stack_deps.

  Args:
    stacktrace (Stacktrace): Parsed stacktrace object.
    stack_deps (dict): Represents all the dependencies show in
      the crash stack.

  Returns:
    A dict, maps dep path to a dict mapping file path to a list of stack
    inforamtion of this file. A file may occur in several frames, one stack info
    consist of a StackFrame and the callstack priority of it.

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


def GetBlameForFilesGroupedByDeps(stacktrace, stack_deps):
  """Gets Blames of files in stacktrace for deps in stack_deps.

  Args:
    stacktrace (Stacktrace): Parsed stacktrace object.
    stack_deps (dict of Dependencys): Represents all the dependencies shown in
      the crash stack.

  Returns:
    A dict, maps dep_path to a dict mapping file path to its Blame.

    For example:
    {
        'src/': {
            'a.cc': Blame(revision, 'a.cc')
            'b.cc': Blame(revision, 'b.cc')
        }
    }
  """
  dep_to_file_to_blame = defaultdict(dict)

  for callstack in stacktrace:
    for frame in callstack:
      # We only care about those dependencies in crash stack.
      if frame.dep_path not in stack_deps:
        continue

      git_repository = GitRepository(stack_deps[frame.dep_path].repo_url,
                                     HttpClientAppengine())
      dep_to_file_to_blame[frame.dep_path][frame.file_path] = (
          git_repository.GetBlame(
              frame.file_path, stack_deps[frame.dep_path].revision))

  return dep_to_file_to_blame


def FindMatchResults(dep_to_file_to_changelogs,
                     dep_to_file_to_stack_infos,
                     dep_to_file_to_blame,
                     ignore_cls=None):
  """Finds results by matching stacktrace and changelogs in regression range.

  This method only applies to those crashes with regression range.

  Args:
    dep_to_file_to_changelogs (dict): Maps dep_path to a dict mapping file path
      to ChangeLogs that touched this file.
    dep_to_file_to_stack_infos (dict): Maps dep path to a dict mapping file path
      to a list of stack inforamtion of this file. A file may occur in several
      frames, one stack info consist of a StackFrame and the callstack priority
      of it.
    dep_to_file_to_blame (dict): Maps dep_path to a dict mapping file path to
      its Blame.
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

        match_results.GenerateMatchResults(
            crashed_file_path, dep, stack_infos, changelogs,
            dep_to_file_to_blame[dep][crashed_file_path])

  return match_results.values()


def FindItForCrash(stacktrace, regression_deps_rolls, crashed_deps):
  """Finds culprit results for crash.

  Args:
    stacktrace (Stactrace): Parsed Stactrace object.
    regression_deps_rolls (dict): Maps dep_path to DependencyRoll in
      regression range.
    crashed_deps (dict of Dependencys): Represents all the dependencies of
      crashed revision.

  Returns:
    List of dicts of culprit results, sorted by confidence from highest to
    lowest.
  """
  if not regression_deps_rolls:
    return []

  # We are only interested in the deps in crash stack (the callstack that
  # caused the crash).
  stack_deps = GetDepsInCrashStack(stacktrace.GetCrashStack(), crashed_deps)

  # Get dep and file to changelogs, stack_info and blame dicts.
  dep_to_file_to_changelogs, ignore_cls = GetChangeLogsForFilesGroupedByDeps(
      regression_deps_rolls, stack_deps)
  dep_to_file_to_stack_infos = GetStackInfosForFilesGroupedByDeps(
      stacktrace, stack_deps)
  dep_to_file_to_blame = GetBlameForFilesGroupedByDeps(stacktrace, stack_deps)

  results = FindMatchResults(dep_to_file_to_changelogs,
                             dep_to_file_to_stack_infos,
                             dep_to_file_to_blame,
                             ignore_cls)

  if not results:
    return []

  aggregator = Aggregator([TopFrameIndex(), MinDistance()])

  map(aggregator.ScoreAndReason, results)

  return sorted([result.ToDict() for result in results],
                key=lambda r: -r['confidence'])
