# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import os
import re

from common.diff import ChangeType
from waterfall.failure_signal import FailureSignal


def _IsSameFile(changed_src_file_path, file_path_in_log):
  """Guesses if the two files are the same.

  Args:
    changed_src_file_path (str): Full path of a file committed to git repo.
    file_path_in_log (str): Path of a file appearing in a failure log. It might
        not be a full path.

  Returns:
    True if the two files are likely the same, otherwise False. Eg.:
      True: (chrome/test/base/chrome_process_util.h, base/chrome_process_util.h)
      True: (a/b/x.cc, a/b/x.cc)
      False: (c/x.cc, a/b/c/x.cc)
  """
  if changed_src_file_path == file_path_in_log:
    return True
  return changed_src_file_path.endswith('/%s' % file_path_in_log)


def _NormalizeObjectFilePath(file_path):
  """Normalize the file path to an c/c++ object file.

  During compile, a/b/c/file.cc in TARGET will be compiled into object file
  obj/a/b/c/TARGET.file.o, thus 'obj/' and TARGET need to be removed from path.

  Args:
    file_path (str): A path to an object file (.o or .obj) after compile.
  Returns:
    A normalized file path.
  """
  if file_path.startswith('obj/'):
    file_path = file_path[4:]
  file_dir = os.path.dirname(file_path)
  file_name = os.path.basename(file_path)
  parts = file_name.split('.', 1)
  if len(parts) == 2 and (parts[1].endswith('.o') or parts[1].endswith('.obj')):
    file_name = parts[1]

  if file_dir:
    return '%s/%s' % (file_dir, file_name)
  else:
    return file_name


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


def _IsRelated(changed_src_file_path, file_path):
  """Checks if two files are related.

  Example of related files:
    1. file.h <-> file_impl.cc
    2. file_impl.cc <-> file_unittest.cc
    3. file_win.cc <-> file_mac.cc
    4. x.h <-> x.cc
  """
  if file_path.endswith('.o') or file_path.endswith('.obj'):
    file_path = _NormalizeObjectFilePath(file_path)

  if _IsSameFile(_StripExtensionAndCommonSuffix(changed_src_file_path),
                 _StripExtensionAndCommonSuffix(file_path)):
    return True

  return False


class _Justification(object):
  """Justification for why a CL might be suspected for a build failure.

  A justification includes:
  1. score:
     1) If a hint shows that a CL is highly-suspected, the hint is given 5
        score points. Eg. a CL is highly suspected if it deleted a .cc file
        appearing in the compile failure.
     2) If a hint shows that a CL is likely-suspected, the hint is given 1
        score point. Eg. a CL is just likely suspected if it only changed a
        related file (x_impl.cc vs. x.h) appearing in a failure.
  2. hints: each hint is a string describing a reason for suspecting a CL and
     could be shown to the user (eg., "added x_impl.cc (and it was in log)").
  """

  def __init__(self):
    self._score = 0
    self._hints = collections.defaultdict(int)

  @property
  def score(self):
    return self._score

  def AddFileChange(self, change_action, changed_src_file_path,
                    file_path_in_log, score):
    """Adds a suspected file change.

    Args:
      change_action (str): How file was changed: added, deleted, or modified.
      changed_src_file_path (str): Changed file path in a CL.
      file_path_in_log (str): File path appearing in the failure log.
      score (int): Score number for the file change.
    """
    changed_src_file_path = os.path.basename(changed_src_file_path)
    file_path_in_log = os.path.basename(file_path_in_log)

    if changed_src_file_path != file_path_in_log:
      hint = '%s %s (%s was in log)' % (
          change_action, changed_src_file_path, file_path_in_log)
    else:
      hint = '%s %s (and it was in log)' % (
          change_action, changed_src_file_path)

    self._hints[hint] += score
    self._score += score

  def ToDict(self):
    return {
        'score': self._score,
        'hints': self._hints,
    }


def _CheckFile(change_action, changed_src_file_path, file_path_in_log,
               score, justification):
  """Checks if the given files are related and updates the justification.

  Args:
    change_action (str): How file was changed: added, deleted, or modified.
    changed_src_file_path (str): Changed file path in a CL.
    file_path_in_log (str): File path appearing in the failure log.
    score (int): Score number if two files are the same.
    justification (_Justification): An instance of _Justification.
  """
  if _IsSameFile(changed_src_file_path, file_path_in_log):
    justification.AddFileChange(change_action, changed_src_file_path,
                                file_path_in_log, score)
  elif _IsRelated(changed_src_file_path, file_path_in_log):
    # For related files, do score=1, because it is just likely-suspected, not
    # highly-suspected.
    justification.AddFileChange(
        change_action, changed_src_file_path, file_path_in_log, 1)


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

  for file_path_in_log, _ in failure_signal.files.iteritems():
    # TODO(stgao): remove this hack when DEPS parsing is supported.
    if file_path_in_log.startswith('src/'):
      file_path_in_log = file_path_in_log[4:]

    for touched_file in change_log['touched_files']:
      change_type = touched_file['change_type']

      # TODO: move the analysis of change type into function _CheckFile.
      if change_type == ChangeType.MODIFY:
        if _IsSameFile(touched_file['new_path'], file_path_in_log):
          # TODO(stgao): use line number for git blame.
          justification.AddFileChange(
              'modified', touched_file['new_path'], file_path_in_log, 1)
        elif _IsRelated(touched_file['new_path'], file_path_in_log):
          justification.AddFileChange(
              'modified', touched_file['new_path'], file_path_in_log, 1)

      if change_type in (ChangeType.ADD, ChangeType.COPY, ChangeType.RENAME):
        _CheckFile('added', touched_file['new_path'], file_path_in_log, 5,
                   justification)

      if change_type in (ChangeType.DELETE, ChangeType.RENAME):
        _CheckFile('deleted', touched_file['old_path'], file_path_in_log, 5,
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
              'score': 11,
              'hints': {
                'add a/b/x.cc': 5,
                'delete a/b/y.cc': 5,
                'modify e/f/z.cc': 1,
                ...
              }
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

    # TODO(stgao): sort CLs by score.
    analysis_result['failures'].append(step_analysis_result)

  return analysis_result
