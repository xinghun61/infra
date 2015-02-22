# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import os
import re

from common.diff import ChangeType
from waterfall.failure_signal import FailureSignal


def _IsSameFile(src_file, file_path):
  """Guesses if the two files are the same.

  Args:
    src_file (str): Full path of a file committed to git repo.
    file_path (str): Path of a file appearing in a failure log. It might not be
        a full path.

  Returns:
    True if the two files are likely the same, otherwise False. Eg.:
      True: (chrome/test/base/chrome_process_util.h, base/chrome_process_util.h)
      True: (a/b/x.cc, a/b/x.cc)
      False: (c/x.cc, a/b/c/x.cc)
  """
  if src_file == file_path:
    return True
  return src_file.endswith('/%s' % file_path)


def _NormalizeObjectFile(file_path):
  # During compile, a/b/c/file.cc in TARGET will be compiled into object
  # file a/b/c/TARGET.file.o, thus TARGET needs removing from path.
  if file_path.startswith('obj/'):
    file_path = file_path[4:]
  file_dir = os.path.dirname(file_path)
  file_name = os.path.basename(file_path)
  parts = file_name.split('.', 1)
  if len(parts) == 2 and parts[1].endswith('.o'):
    file_name = parts[1]

  return os.path.join(file_dir, file_name).replace(os.sep, '/')


_COMMON_SUFFIXES = [
    'impl',
    'browser_tests', 'browser_test', 'browsertest', 'browsertests',
    'unittests', 'unittest', 'tests', 'test',
    'gcc', 'msvc',
    'arm', 'arm64', 'mips', 'portable', 'x86',
    'android', 'ios', 'linux', 'mac', 'ozone', 'posix', 'win',
    'aura', 'x', 'x11',
]

_COMMON_SUFFIX_PATTERNS = [
    re.compile('.*(_%s)$' % suffix) for suffix in _COMMON_SUFFIXES
]


def _StripExtensionAndCommonSuffix(file_path):
  """Strips extension and common suffixes from file name to guess relation.

  Examples:
    file_impl.cc, file_unittest.cc, file_impl_mac.h -> file
  """
  file_dir = os.path.dirname(file_path)
  file_name = os.path.splitext(os.path.basename(file_path))[0]
  while True:
    match = None
    for suffix_patten in _COMMON_SUFFIX_PATTERNS:
      match = suffix_patten.match(file_name)
      if match:
        file_name = file_name[:-len(match.group(1))]
        break

    if not match:
      break

  return os.path.join(file_dir, file_name).replace(os.sep, '/')


def _IsRelated(src_file, file_path):
  """Checks if two files are related.

  Example of related files:
    1. file.h <-> file_impl.cc
    2. file_impl.cc <-> file_unittest.cc
    3. file_win.cc <-> file_mac.cc
    4. x.h <-> x.cc
  """
  if file_path.endswith('.o'):
    file_path = _NormalizeObjectFile(file_path)

  if _IsSameFile(_StripExtensionAndCommonSuffix(src_file),
                 _StripExtensionAndCommonSuffix(file_path)):
    return True

  return False


class _Justification(object):
  """Justification for why a CL might be suspected for a build failure.

  A justification includes:
  1. suspect points: for a highly-suspected CL, it is given some suspect points.
     Eg. a CL is highly suspected if it deleted a .cc file appearing in the
     compile failure.
  2. score: for a likely-suspected CL, it won't get suspect points, but a score.
     Eg. a CL is just likely suspected if it only changed a related file
     (x_impl.cc vs. x.h) appearing in a test failure.
     For a highly-suspected CL, it will get a high score besides suspect points.
  3. hints: each hint is a string describing a reason for suspecting a CL and
    could be shown to the user (eg., "add x_impl.cc").
  """

  def __init__(self):
    self._suspect_points = 0
    self._score = 0
    self._hints = []

  @property
  def score(self):
    return self._score

  def AddFileChange(
      self, change_action, src_file, file_path, suspect_points, score):
    """Adds a suspected file change.

    Args:
      change_action (str): One of the change types in common.diff.ChangeType.
      src_file (str): Changed file path in a CL.
      file_path (str): File path appearing in the failure log.
      suspect_points (int): Number of suspect points for the file change.
      score (int): Score number for the file change.
    """
    self._suspect_points += suspect_points
    self._score += score

    # TODO: make hint more descriptive?
    if src_file != file_path:
      self._hints.append(
          '%s %s (%s)' % (change_action, src_file, file_path))
    else:
      self._hints.append('%s %s' % (change_action, src_file))

  def ToDict(self):
    return {
        'suspect_points': self._suspect_points,
        'score': self._score,
        'hints': self._hints,
    }


def _CheckFile(
    change_action, src_file, file_path, suspect_points, score, justification):
  """Checks if the given files are the same or correlated.

  Args:
    change_action (str): One of the change types in common.diff.ChangeType.
    src_file (str): Changed file path in a CL.
    file_path (str): File path appearing in the failure log.
    suspect_points (int): Number of suspect points if two files are the same.
    score (int): Score number if two files are the same.
    justification (_Justification): An instance of _Justification.
  """
  if _IsSameFile(src_file, file_path):
    justification.AddFileChange(
        change_action, src_file, file_path, suspect_points, score)
  elif _IsRelated(src_file, file_path):
    # For correlated files, do suspect=0 and score=1, because it is just likely,
    # but not highly, suspected.
    justification.AddFileChange(
        change_action, src_file, file_path, 0, 1)


def _CheckFiles(failure_signal, change_log):
  """Check files in the given change log of a CL against the failure signal.

  Args:
    failure_signal (FailureSignal): The failure signal of a failed step or test.
    change_log (dict): The change log of a CL as returned by
        common.change_log.ChangeLog.ToJson().  # TODO(stgao): ToJson -> ToDict.

  Returns:
    A dict as returned by _Justification.ToDict() if the CL is suspected for the
    failure; otherwise None.
  """
  justification = _Justification()

  for file_path, _ in failure_signal.files.iteritems():
    # TODO(stgao): remove this hack when DEPS parsing is supported.
    if file_path.startswith('src/'):
      file_path = file_path[4:]

    for touched_file in change_log['touched_files']:
      change_type = touched_file['change_type']

      if change_type == ChangeType.MODIFY:
        if _IsSameFile(touched_file['new_path'], file_path):
          # TODO(stgao): use line number for git blame.
          justification.AddFileChange(
              'modify', touched_file['new_path'], file_path, 0, 1)
        elif _IsRelated(touched_file['new_path'], file_path):
          justification.AddFileChange(
              'modify', touched_file['new_path'], file_path, 0, 1)

      if change_type in (ChangeType.ADD, ChangeType.COPY, ChangeType.RENAME):
        _CheckFile('add', touched_file['new_path'], file_path, 1, 5,
                   justification)

      if change_type in (ChangeType.DELETE, ChangeType.RENAME):
        _CheckFile('delete', touched_file['old_path'], file_path, 1, 5,
                   justification)

  if not justification.score:
    return None
  else:
    return justification.ToDict()


def AnalyzeBuildFailure(failure_info, change_logs, failure_signals):
  """Analyze the given failure signals, and figure out culprit CLs.

  Args:
    failure_info (dict): Output of pipeline DetectFirstFailurePipeline.
    change_logs (dict): Output of pipeline PullChangelogPipeline.
    failure_signals (dict): Output of pipeline ExtractSignalPipeline.

  Returns:
    A dict with the following form:
    {
      'failures': [
        {
          'step_name': 'compile',
          'first_failure': 230,
          'last_pass': 229,
          'suspected_cls': [
            {
              'build_number': 230,
              'dependency_name': 'chromium',
              'revision': 'a_git_hash',
              'commit_position': 56789,
              'suspect_points': 2,
              'score': 11,
              'hints': [
                'add a/b/x.cc',
                'delete a/b/y.cc',
                'modify e/f/z.cc',
                ...
              ]
            },
            ...
          ],
        },
        ...
      ]
    }
  """
  analysis_result = {
      'failures': []
  }

  if not failure_info['failed']:
    return analysis_result

  def CreateCLInfoDict(justification_dict, build_number, change_log):
    # TODO(stgao): remove hard-coded 'chromium' when DEPS file parsing is
    # supported.
    cl_info = {
        'build_number': build_number,
        'dependency_name': 'chromium',
        'revision': change_log['revision'],
        'commit_position': change_log.get('commit_position'),
        'code_review_url': change_log.get('code_review_url'),
    }

    cl_info.update(justification_dict)
    return cl_info

  failed_steps = failure_info['failed_steps']
  builds = failure_info['builds']
  for step_name, step_failure_info in failed_steps.iteritems():
    failure_signal = FailureSignal.FromJson(failure_signals[step_name])
    failed_build_number = step_failure_info['current_failure']
    build_number = step_failure_info['first_failure']

    step_analysis_result = {
        'step_name': step_name,
        'first_failure': step_failure_info['first_failure'],
        'last_pass': step_failure_info.get('last_pass'),
        'suspected_cls': [],
    }

    while build_number <= failed_build_number:
      for revision in builds[str(build_number)]['blame_list']:
        justification_dict = _CheckFiles(failure_signal, change_logs[revision])

        if not justification_dict:
          continue

        step_analysis_result['suspected_cls'].append(
            CreateCLInfoDict(justification_dict, build_number,
                             change_logs[revision]))

      build_number += 1

    # TODO(stgao): sort CLs by suspect points and score.
    analysis_result['failures'].append(step_analysis_result)

  return analysis_result
