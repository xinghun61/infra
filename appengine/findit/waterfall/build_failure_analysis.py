# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import os
import re

from google.appengine.ext import ndb

from common.waterfall import failure_type
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import analysis_status
from libs import time_util
from libs.deps import chrome_dependency_fetcher
from libs.gitiles.diff import ChangeType
from model import analysis_approach_type
from model import result_status
from model.wf_analysis import WfAnalysis
from services import deps
from waterfall import suspected_cl_util
from waterfall import waterfall_config
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
  changed_src_file_path_lower = changed_src_file_path.lower()
  file_path_in_log_lower = file_path_in_log.lower()

  if changed_src_file_path_lower == file_path_in_log_lower:
    return True
  return changed_src_file_path_lower.endswith('/%s' % file_path_in_log_lower)


def _GetGitBlame(repo_info, touched_file_path):
  """Gets git blames of touched_file.

  Args:
    repo_info (dict): The repo_url and revision for the build cycle.
    touched_file_path (str): Full path of a file in change_log.
  """
  if repo_info:
    repo_url = repo_info['repo_url']
    git_repo = CachedGitilesRepository(HttpClientAppengine(), repo_url)
    revision = repo_info['revision']
    return git_repo.GetBlame(touched_file_path, revision)


def _GetChangedLinesForChromiumRepo(repo_info, touched_file, line_numbers,
                                    suspected_revision):
  """Checks if the CL made change close to the failed line in log.

  Args:
    repo_info (dict): The repo_url and revision for the build cycle.
    touched_file (dict): The touched file found in the change log.
    line_numbers (list): List of line_numbers mentioned in the failure log.
    suspected_revision (str): Git hash revision of the suspected CL.

  Returns:
    A list of lines which are mentioned in log and changed in cl.
  """
  changed_line_numbers = []
  if line_numbers:
    blame = _GetGitBlame(repo_info, touched_file['new_path'])
    if blame:
      for line_number in line_numbers:
        for region in blame:
          if region.revision == suspected_revision:
            if (line_number >= region.start and
                line_number <= region.start + region.count - 1):
              changed_line_numbers.append(line_number)

  return changed_line_numbers


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
    object_file = parts[1]
    name = os.path.splitext(object_file)[0]
    # Special case for file.cc.obj and similar cases.
    if name not in ['c', 'cc', 'cpp', 'm', 'mm']:
      file_name = parts[1]

  if file_dir:
    return '%s/%s' % (file_dir, file_name)
  else:
    return file_name


_COMMON_SUFFIXES = [
    'impl',
    'browser_tests',
    'browser_test',
    'browsertest',
    'browsertests',
    'unittests',
    'unittest',
    'tests',
    'test',
    'gcc',
    'msvc',
    'arm',
    'arm64',
    'mips',
    'portable',
    'x86',
    'android',
    'ios',
    'linux',
    'mac',
    'ozone',
    'posix',
    'win',
    'aura',
    'x',
    'x11',
]

_COMMON_TEST_SUFFIXES = [
    'browser_tests',
    'browser_test',
    'browsertest',
    'browsertests',
    'unittests',
    'unittest',
    'tests',
    'test',
]

_COMMON_SUFFIX_PATTERNS = [
    re.compile('.*(_%s)$' % suffix) for suffix in _COMMON_SUFFIXES
]

_COMMON_TEST_SUFFIX_PATTERNS = [
    re.compile('.*(_%s)$' % suffix) for suffix in _COMMON_TEST_SUFFIXES
]

_RELATED_FILETYPES = [['h', 'hh'
                       'c', 'cc', 'cpp', 'm', 'mm', 'o', 'obj'], ['py', 'pyc'],
                      ['gyp', 'gypi']]


def _AreBothFilesTestRelated(changed_src_file_path, file_in_log_path):
  """Tests if both file names contain test-related suffixes."""
  changed_file_name = os.path.splitext(
      os.path.basename(changed_src_file_path))[0]
  file_in_log_name = os.path.splitext(os.path.basename(file_in_log_path))[0]

  is_changed_file_test_related = False
  is_file_in_log_test_related = False

  for test_suffix_patten in _COMMON_TEST_SUFFIX_PATTERNS:
    if test_suffix_patten.match(changed_file_name):
      is_changed_file_test_related = True
    if test_suffix_patten.match(file_in_log_name):
      is_file_in_log_test_related = True

  return is_changed_file_test_related and is_file_in_log_test_related


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


def _GetRelatedExtensionsList(extension):
  for related_filetype_list in _RELATED_FILETYPES:
    if extension in related_filetype_list:
      return related_filetype_list
  return []


def _IsRelated(changed_src_file_path, file_path):
  """Checks if two files are related.

  Example of related files:
    1. file.h <-> file_impl.cc
    2. file_impl.cc <-> file_unittest.cc
    3. file_win.cc <-> file_mac.cc
    4. x.h <-> x.cc

  Example of not related files:
    1. a_tests.py <-> a_browsertests.py
    2. a.isolate <-> a.cc
    3. a.py <-> a.cpp
  """
  changed_src_file_extension = os.path.splitext(changed_src_file_path)[1][1:]
  file_path_extension = os.path.splitext(file_path)[1][1:]

  if file_path_extension not in _GetRelatedExtensionsList(
      changed_src_file_extension):
    return False

  if file_path.endswith('.o') or file_path.endswith('.obj'):
    file_path = _NormalizeObjectFilePath(file_path)

  if _AreBothFilesTestRelated(changed_src_file_path, file_path):
    return False

  if _IsSameFile(
      _StripExtensionAndCommonSuffix(changed_src_file_path),
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
    self._hints = defaultdict(int)

  @property
  def score(self):
    return self._score

  def AddFileChange(self,
                    change_action,
                    changed_src_file_path,
                    file_path_in_log,
                    score,
                    num_file_name_occurrences,
                    changed_line_numbers=None,
                    check_dependencies=False):
    """Adds a suspected file change.

    Args:
      change_action (str): How file was changed: added, deleted, or modified.
      changed_src_file_path (str): Changed file path in a CL.
      file_path_in_log (str): File path appearing in the failure log.
      score (int): Score number for the file change.
      num_file_name_occurrences (int): Number of occurrences of this file base
          name (not including directory part) in the commit.
      changed_line_numbers (list): List of lines which are verified in both
          failure log and git blame.
      check_dependencies: Boolean representing if file_path_in_log is from
          dependencies found by ninja.
    """
    if num_file_name_occurrences == 1:
      changed_src_file_path = os.path.basename(changed_src_file_path)
      file_path_in_log = os.path.basename(file_path_in_log)

    if changed_src_file_path != file_path_in_log:
      hint = '%s %s (%s was in log)' % (change_action, changed_src_file_path,
                                        file_path_in_log)
    else:
      if changed_line_numbers:
        hint = '%s %s[%s] (and it was in log)' % (
            change_action, changed_src_file_path,
            ', '.join(map(str, changed_line_numbers)))
      else:
        hint = '%s %s (and it was in log)' % (change_action,
                                              changed_src_file_path)

    if check_dependencies:
      self._score = 2
      hint = hint.replace('in log', 'in dependencies found by ninja')
      self._hints[hint] = self._score
    else:
      self._score += score
      self._hints[hint] += score

  def AddDEPSRoll(self, change_action, dep_path, dep_repo_url, dep_new_revision,
                  dep_old_revision, file_path_in_log, score,
                  changed_line_numbers, roll_file_change_type):
    if dep_old_revision is not None and dep_new_revision is not None:
      url_to_changes_in_roll = '%s/+log/%s..%s?pretty=fuller' % (
          dep_repo_url, dep_old_revision[:12], dep_new_revision[:12])
    elif dep_new_revision is not None:
      url_to_changes_in_roll = '%s/+log/%s' % (dep_repo_url, dep_new_revision)
    else:  # New revision is None. (Old revision should not be None.)
      url_to_changes_in_roll = '%s/+log/%s' % (dep_repo_url, dep_old_revision)

    if roll_file_change_type == ChangeType.ADD:
      hint = ('%s dependency %s with changes in %s '
              '(and %s(added) was in log)' %
              (change_action, dep_path, url_to_changes_in_roll,
               file_path_in_log))
    elif roll_file_change_type == ChangeType.DELETE:
      hint = ('%s dependency %s with changes in %s '
              '(and %s(deleted) was in log)' %
              (change_action, dep_path, url_to_changes_in_roll,
               file_path_in_log))
    elif changed_line_numbers:
      hint = ('%s dependency %s with changes in %s (and %s[%s] was in log)' %
              (change_action, dep_path, url_to_changes_in_roll,
               file_path_in_log, ', '.join(map(str, changed_line_numbers))))
    else:
      hint = ('%s dependency %s with changes in %s (and %s was in log)' %
              (change_action, dep_path, url_to_changes_in_roll,
               file_path_in_log))

    self._hints[hint] = score
    self._score += score

  def ToDict(self):
    return {
        'score': self._score,
        'hints': self._hints,
    }


def _CheckFile(touched_file,
               file_path_in_log,
               justification,
               file_name_occurrences,
               line_numbers,
               repo_info,
               suspected_revision,
               check_dependencies=False):
  """Checks if the given files are related and updates the justification.

  Args:
    touched_file (dict): The touched file found in the change log.
    file_path_in_log (str): File path appearing in the failure log.
    justification (_Justification): An instance of _Justification.
    file_name_occurrences (dict): A dict mapping file names to
        number of occurrences.
    line_numbers(list): A list of line numbers of 'file_path_in_log' which
        appears in failure log.
    repo_info (dict): The repo_url and revision for the build cycle.
    suspected_revision (str): Git hash revision of the suspected CL.
    check_dependencies (bool): A boolean indicating if file_path_in_log is
        from dependencies given by ninja output.
  """
  change_type = touched_file['change_type']

  if change_type == ChangeType.MODIFY:
    changed_src_file_path = touched_file['new_path']
    file_name = os.path.basename(changed_src_file_path)

    score = 0
    changed_line_numbers = None
    if _IsSameFile(changed_src_file_path, file_path_in_log):
      changed_line_numbers = _GetChangedLinesForChromiumRepo(
          repo_info, touched_file, line_numbers, suspected_revision)
      if changed_line_numbers:
        score = 4
      else:
        score = 2
    elif _IsRelated(changed_src_file_path, file_path_in_log):
      score = 1

    if score:
      justification.AddFileChange('modified', changed_src_file_path,
                                  file_path_in_log, score,
                                  file_name_occurrences.get(file_name),
                                  changed_line_numbers, check_dependencies)

  if change_type in (ChangeType.ADD, ChangeType.COPY, ChangeType.RENAME):
    changed_src_file_path = touched_file['new_path']
    file_name = os.path.basename(changed_src_file_path)

    score = 0
    if _IsSameFile(changed_src_file_path, file_path_in_log):
      score = 5
    elif _IsRelated(changed_src_file_path, file_path_in_log):
      score = 1

    if score:
      justification.AddFileChange(
          'added',
          changed_src_file_path,
          file_path_in_log,
          score,
          file_name_occurrences.get(file_name),
          check_dependencies=check_dependencies)

  if change_type in (ChangeType.DELETE, ChangeType.RENAME):
    changed_src_file_path = touched_file['old_path']
    file_name = os.path.basename(changed_src_file_path)

    score = 0
    if _IsSameFile(changed_src_file_path, file_path_in_log):
      score = 5
    elif _IsRelated(changed_src_file_path, file_path_in_log):
      score = 1

    if score:
      justification.AddFileChange(
          'deleted',
          changed_src_file_path,
          file_path_in_log,
          score,
          file_name_occurrences.get(file_name),
          check_dependencies=check_dependencies)


def _StripChromiumRootDirectory(file_path):
  # Strip src/ from file path to make all files relative to the chromium root
  # directory.
  if file_path.startswith('src/'):
    file_path = file_path[4:]
  return file_path


def _GetChangeTypeAndCulpritCommit(file_path_in_log, roll_repo,
                                   commits_between_revisions):
  """Determines the first commit that touches a file within a revision range.

  Args:
    file_path_in_log: The file to search each commit's change logs for.
    roll_repo: A git repository object to make requests to git for changes logs.
    commits_between_revisions: A list of revisions to request change logs.

  Returns:
    The modification type made to file_path_in_log if found.
    The corresponding commit that touched file_path_in_log if found.
  """
  for commit in commits_between_revisions:
    # Use the change log for each commit to determine if and how
    # file_path_in_log log was modified.
    change_log = roll_repo.GetChangeLog(commit)
    for file_change_info in change_log.touched_files:
      if file_change_info.change_type in (ChangeType.DELETE, ChangeType.RENAME):
        changed_src_file_path = file_change_info.old_path
      else:
        changed_src_file_path = file_change_info.new_path

      if _IsSameFile(changed_src_file_path, file_path_in_log):
        # Found the file and the commit that modified it.
        # TODO(lijeffrey): It is possible multiple commits modified the file.
        return file_change_info.change_type, commit

      # TODO(lijeffrey): It is possible _IsRelated(changed_src_file_path,
      # file_path_in_log) may also provide useful information, but how is not
      # yet determined.

  return None, None


def _GetChangedLinesForDependencyRepo(roll, file_path_in_log, line_numbers):
  """Gets changed line numbers for file in failure log.

    Tests if the same lines mentioned in failure log are changed within
    the DEPS roll, if so, return those line numbers.
  """
  roll_repo = CachedGitilesRepository(HttpClientAppengine(), roll['repo_url'])
  old_revision = roll['old_revision']
  new_revision = roll['new_revision']
  old_change_log = roll_repo.GetChangeLog(old_revision)
  old_rev_author_time = old_change_log.author.time
  new_change_log = roll_repo.GetChangeLog(new_revision)
  new_rev_author_time = new_change_log.author.time

  file_change_type = None
  changed_line_numbers = []

  if old_rev_author_time >= new_rev_author_time:
    # If the DEPS roll is downgrade, bail out.
    return file_change_type, changed_line_numbers

  commits_in_roll = roll_repo.GetCommitsBetweenRevisions(
      old_revision, new_revision)

  file_change_type, culprit_commit = _GetChangeTypeAndCulpritCommit(
      file_path_in_log, roll_repo, commits_in_roll)

  if culprit_commit is None:
    # Bail out if no commits touched the file in the log.
    return file_change_type, changed_line_numbers

  if file_change_type == ChangeType.MODIFY:
    # If the file was modified, use the blame information to determine which
    # lines were changed.
    blame = roll_repo.GetBlame(file_path_in_log, culprit_commit)

    if not blame:
      return file_change_type, changed_line_numbers

    for region in blame:
      if line_numbers:
        for line_number in line_numbers:
          if (line_number >= region.start and
              line_number <= region.start + region.count - 1 and
              region.revision in commits_in_roll):
            # One line which appears in the failure log is changed within
            # the DEPS roll.
            changed_line_numbers.append(line_number)

  return file_change_type, changed_line_numbers


def _CheckFileInDependencyRolls(file_path_in_log,
                                rolls,
                                justification,
                                line_numbers=None):
  """Checks if the file is in a dependency roll and updates the justification.

  Args:
    file_path_in_log (str): File path appearing in the failure log.
    rolls (list): A list of dependency rolls made by a single commit/CL, each
        roll is a dict in the following form:
        {
          'path': 'path/to/dependency',
          'repo_url': 'https://url/to/dep.git',
          'old_revision': 'git_hash1',
          'new_revision': 'git_hash2'
        }
    justification (_Justification): An instance of _Justification.
    line_numbers (list): List of line_numbers mentioned in the failure log.
  """
  for roll in rolls:
    if roll['path'] == 'src/v8/':
      # Cannot compare author time for v8 roll, author time for CLs during the
      # roll may be earlier than the author time of old revision.
      # TODO: Figure out the rolling mechanism of v8 to add logic for checking
      # this repo.
      continue

    change_action = None
    dep_path = _StripChromiumRootDirectory(roll['path'])
    if not file_path_in_log.startswith(dep_path):
      continue

    changed_lines = []
    roll_file_change_type = None
    if roll['old_revision'] and roll['new_revision']:
      roll_file_change_type, changed_lines = _GetChangedLinesForDependencyRepo(
          roll, file_path_in_log[len(dep_path):], line_numbers)

      if not roll_file_change_type:
        continue

      change_action = 'rolled'
      if (roll_file_change_type == ChangeType.ADD or
          roll_file_change_type == ChangeType.DELETE):
        # File was either added or deleted.
        score = 5
      elif not changed_lines:
        # File is changed, but not the same line.
        score = 1
      else:
        # The lines which appear in the failure log are changed.
        score = 4
    elif roll['new_revision']:
      change_action = 'added'
      score = 5
    else:  # New revision is None. (Old revision should not be None.)
      change_action = 'deleted'
      score = 5

    justification.AddDEPSRoll(change_action, dep_path, roll['repo_url'],
                              roll['new_revision'], roll['old_revision'],
                              file_path_in_log[len(dep_path):], score,
                              changed_lines, roll_file_change_type)


def _CheckFiles(failure_signal, change_log, deps_info,
                check_dependencies=False):
  """Checks files in the given change log of a CL against the failure signal.

  Args:
    failure_signal (FailureSignal): The failure signal of a failed step or test.
    change_log (dict): The change log of a CL as returned by
        common.change_log.ChangeLog.ToDict().
    deps_info (dict): Output of pipeline ExtractDEPSInfoPipeline.
    check_dependencies (bool): If it's true check ninja dependencies.

  Returns:
    A dict as returned by _Justification.ToDict() if the CL is suspected for the
    failure; otherwise None.
  """
  # Use a dict to map each file name of the touched files to their occurrences.
  file_name_occurrences = defaultdict(int)
  for touched_file in change_log['touched_files']:
    change_type = touched_file['change_type']
    if (change_type in (ChangeType.ADD, ChangeType.COPY, ChangeType.RENAME,
                        ChangeType.MODIFY)):
      file_name = os.path.basename(touched_file['new_path'])
      file_name_occurrences[file_name] += 1

    if change_type in (ChangeType.DELETE, ChangeType.RENAME):
      file_name = os.path.basename(touched_file['old_path'])
      file_name_occurrences[file_name] += 1

  justification = _Justification()

  rolls = deps_info.get('deps_rolls', {}).get(change_log['revision'], [])
  repo_info = deps_info.get('deps', {}).get('src/', {})

  if not check_dependencies:
    for file_path_in_log, line_numbers in failure_signal.files.iteritems():
      file_path_in_log = _StripChromiumRootDirectory(file_path_in_log)

      for touched_file in change_log['touched_files']:
        _CheckFile(touched_file, file_path_in_log, justification,
                   file_name_occurrences, line_numbers, repo_info,
                   change_log['revision'])

      _CheckFileInDependencyRolls(file_path_in_log, rolls, justification,
                                  line_numbers)
  else:
    for failed_edge in failure_signal.failed_edges:
      for dependency in failed_edge.get('dependencies'):
        dependency = _StripChromiumRootDirectory(dependency)
        for touched_file in change_log['touched_files']:
          _CheckFile(touched_file, dependency, justification,
                     file_name_occurrences, None, repo_info,
                     change_log['revision'], True)

        _CheckFileInDependencyRolls(dependency, rolls, justification, [])
  if not justification.score:
    return None
  else:
    return justification.ToDict()


class _CLInfo(object):
  """A object of information we need for a suspected CL.

  The information is specific to current build.
  """

  def __init__(self):
    self.failures = defaultdict(list)
    self.top_score = 0
    self.url = None


def _SaveFailureToMap(cl_failure_map, new_suspected_cl_dict, step_name,
                      test_name, top_score):
  """Saves a failure's info to the cl that caused it."""
  cl_key = (new_suspected_cl_dict['repo_name'],
            new_suspected_cl_dict['revision'],
            new_suspected_cl_dict['commit_position'])

  if test_name:
    cl_failure_map[cl_key].failures[step_name].append(test_name)
  else:
    cl_failure_map[cl_key].failures[step_name] = []
  # Ignores the case where in the same build for the same cl,
  # we have different scores.
  # Not sure if we need to handle it since it should be rare.
  cl_failure_map[cl_key].top_score = (cl_failure_map[cl_key].top_score or
                                      top_score)
  cl_failure_map[cl_key].url = (cl_failure_map[cl_key].url or
                                new_suspected_cl_dict['url'])


def _ConvertCLFailureMapToList(cl_failure_map):
  suspected_cls = []
  for cl_key, cl_info in cl_failure_map.iteritems():
    suspected_cl = {}
    (suspected_cl['repo_name'], suspected_cl['revision'],
     suspected_cl['commit_position']) = cl_key
    suspected_cl['url'] = cl_info.url
    suspected_cl['failures'] = cl_info.failures
    suspected_cl['top_score'] = cl_info.top_score

    suspected_cls.append(suspected_cl)
  return suspected_cls


def AnalyzeBuildFailure(failure_info, change_logs, deps_info, failure_signals):
  """Analyzes the given failure signals, and figure out culprit CLs.

  Args:
    failure_info (dict): Output of pipeline DetectFirstFailurePipeline.
    change_logs (dict): Output of pipeline PullChangelogPipeline.
    deps_info (dict): Output of pipeline ExtractDEPSInfoPipeline.
    failure_signals (dict): Output of pipeline ExtractSignalPipeline.

  Returns:
    A dict with the following form:
    {
      'failures': [
        {
          'step_name': 'compile',
          'supported': True
          'first_failure': 230,
          'last_pass': 229,
          'suspected_cls': [
            {
              'build_number': 230,
              'repo_name': 'chromium',
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

    And a list of suspected_cls format as below:
    [
        {
            'repo_name': 'chromium',
            'revision': 'r98_1',
            'commit_position': None,
            'url': None,
            'failures': {
                'b': ['Unittest2.Subtest1', 'Unittest3.Subtest2']
            },
            'top_score': 4
        },
        ...
    ]
  """
  analysis_result = {'failures': []}

  if not failure_info['failed'] or not failure_info['chromium_revision']:
    # Bail out if no failed step or no chromium revision.
    return analysis_result, []

  # Bail out on infra failure
  if failure_info.get('failure_type') == failure_type.INFRA:
    return analysis_result, []

  def CreateCLInfoDict(justification_dict, build_number, change_log):
    # TODO(stgao): remove hard-coded 'chromium' when DEPS file parsing is
    # supported.
    cl_info = {
        'build_number':
            build_number,
        'repo_name':
            'chromium',
        'revision':
            change_log['revision'],
        'commit_position':
            change_log.get('commit_position'),
        'url':
            change_log.get('code_review_url') or change_log.get('commit_url'),
    }

    cl_info.update(justification_dict)
    return cl_info

  failed_steps = failure_info['failed_steps']
  builds = failure_info['builds']
  master_name = failure_info['master_name']

  cl_failure_map = defaultdict(_CLInfo)

  for step_name, step_failure_info in failed_steps.iteritems():
    is_test_level = step_failure_info.get('tests') is not None

    failed_build_number = step_failure_info['current_failure']
    if step_failure_info.get('last_pass') is not None:
      start_build_number = step_failure_info.get('last_pass') + 1
    else:
      start_build_number = step_failure_info['first_failure']
    step_analysis_result = {
        'step_name':
            step_name,
        'first_failure':
            step_failure_info['first_failure'],
        'last_pass':
            step_failure_info.get('last_pass'),
        'suspected_cls': [],
        'supported':
            waterfall_config.StepIsSupportedForMaster(step_name, master_name)
    }

    if is_test_level:
      step_analysis_result['tests'] = []
      for test_name, test_failure in step_failure_info['tests'].iteritems():
        test_analysis_result = {
            'test_name': test_name,
            'first_failure': test_failure['first_failure'],
            'last_pass': test_failure.get('last_pass'),
            'suspected_cls': [],
        }
        step_analysis_result['tests'].append(test_analysis_result)

    if step_analysis_result['supported']:
      for build_number in range(start_build_number, failed_build_number + 1):
        for revision in builds[str(build_number)]['blame_list']:
          if is_test_level:
            # Checks files at test level.
            for test_analysis_result in step_analysis_result['tests']:
              test_name = test_analysis_result['test_name']
              test_signal = FailureSignal.FromDict(
                  failure_signals[step_name]['tests'].get(test_name, {}))

              justification_dict = _CheckFiles(test_signal,
                                               change_logs[revision], deps_info)

              if not justification_dict:
                continue

              new_suspected_cl_dict = CreateCLInfoDict(
                  justification_dict, build_number, change_logs[revision])
              test_analysis_result['suspected_cls'].append(
                  new_suspected_cl_dict)

              _SaveFailureToMap(cl_failure_map, new_suspected_cl_dict,
                                step_name, test_name,
                                max(justification_dict['hints'].values()))

          # Checks Files on step level using step level signals
          # regardless of test level signals so we can make sure
          # no duplicate justifications added to the step result.
          failure_signal = FailureSignal.FromDict(failure_signals[step_name])
          justification_dict = _CheckFiles(failure_signal,
                                           change_logs[revision], deps_info)

          if not justification_dict:
            continue

          new_suspected_cl_dict = CreateCLInfoDict(
              justification_dict, build_number, change_logs[revision])
          step_analysis_result['suspected_cls'].append(new_suspected_cl_dict)

          if not is_test_level:
            _SaveFailureToMap(cl_failure_map, new_suspected_cl_dict, step_name,
                              None, max(justification_dict['hints'].values()))

      if (step_name == 'compile' and
          (waterfall_config.GetDownloadBuildDataSettings()
           .get('use_ninja_output_log'))):
        step_analysis_result['new_compile_suspected_cls'] = []
        for build_number in range(start_build_number, failed_build_number + 1):
          for revision in builds[str(build_number)]['blame_list']:
            failure_signal = FailureSignal.FromDict(failure_signals[step_name])
            justification_dict = _CheckFiles(
                failure_signal, change_logs[revision], deps_info, True)
            if not justification_dict:
              continue

            new_suspected_cl_dict = CreateCLInfoDict(
                justification_dict, build_number, change_logs[revision])

            (step_analysis_result['new_compile_suspected_cls']
             .append(new_suspected_cl_dict))

        if (not step_analysis_result['suspected_cls'] and
            step_analysis_result.get('new_compile_suspected_cls')):
          step_analysis_result['use_ninja_dependencies'] = True
          step_analysis_result['suspected_cls'] = step_analysis_result[
              'new_compile_suspected_cls']
          for new_suspected_cl_dict in step_analysis_result['suspected_cls']:
            # Top score for new heuristic is always 2.
            _SaveFailureToMap(cl_failure_map, new_suspected_cl_dict, step_name,
                              None, 2)

    # TODO(stgao): sort CLs by score.
    analysis_result['failures'].append(step_analysis_result)

  suspected_cls = _ConvertCLFailureMapToList(cl_failure_map)

  return analysis_result, suspected_cls


def PullChangeLogs(failure_info):
  """Pulls change logs for CLs.

  Args:
    failure_info (dict): Output of pipeline DetectFirstFailurePipeline.run().

  Returns:
    A dict with the following form:
    {
      'git_hash_revision1': common.change_log.ChangeLog.ToDict(),
      ...
    }
  """
  git_repo = CachedGitilesRepository(
      HttpClientAppengine(),
      'https://chromium.googlesource.com/chromium/src.git')

  change_logs = {}
  for build in failure_info.get('builds', {}).values():
    for revision in build['blame_list']:
      change_log = git_repo.GetChangeLog(revision)
      if not change_log:
        raise Exception('Failed to get change log for %s' % revision)

      change_logs[revision] = change_log.ToDict()

  return change_logs


def ExtractDepsInfo(failure_info, change_logs):
  """
  Args:
    failure_info (dict): Information about all build failures.
    change_logs (dict): Result of PullChangeLogs().

  Returns:
    A dict with the following form:
    {
      'deps': {
        'path/to/dependency/': {
          'revision': 'git_hash',
          'repo_url': 'https://url/to/dependency/repo.git',
        },
        ...
      },
      'deps_rolls': {
        'git_revision': [
          {
            'path': 'src/path/to/dependency/',
            'repo_url': 'https://url/to/dependency/repo.git',
            'new_revision': 'git_hash1',
            'old_revision': 'git_hash2',
          },
          ...
        ],
        ...
      }
    }
  """
  chromium_revision = failure_info['chromium_revision']
  os_platform = deps.GetOSPlatformName(failure_info['master_name'],
                                       failure_info['builder_name'])

  dep_fetcher = chrome_dependency_fetcher.ChromeDependencyFetcher(
      CachedGitilesRepository.Factory(HttpClientAppengine()))

  return {
      'deps':
          deps.GetDependencies(chromium_revision, os_platform, dep_fetcher),
      'deps_rolls':
          deps.DetectDependencyRolls(change_logs, os_platform, dep_fetcher)
  }


def GetResultAnalysisStatus(analysis_result):
  """Returns the status of the analysis result.

  We can decide the status based on:
    1. whether we found any suspected CL(s).
    2. whether we have triaged the failure.
    3. whether our analysis result is the same as triaged result.
  """
  # Now we can only set the status based on if we found any suspected CL(s).
  # TODO: Add logic to decide the status after comparing with culprit CL(s).
  if not analysis_result or not analysis_result['failures']:
    return None

  any_supported = False
  for failure in analysis_result['failures']:
    if failure['suspected_cls']:
      return result_status.FOUND_UNTRIAGED

    if failure['supported']:
      any_supported = True

  return (result_status.NOT_FOUND_UNTRIAGED
          if any_supported else result_status.UNSUPPORTED)


def _GetSuspectedCLsWithOnlyCLInfo(suspected_cls):
  """Removes failures and top_score from suspected_cls.

  Makes sure suspected_cls from heuristic or try_job have the same format.
  """
  simplified_suspected_cls = []
  for cl in suspected_cls:
    simplified_cl = {
        'repo_name': cl['repo_name'],
        'revision': cl['revision'],
        'commit_position': cl['commit_position'],
        'url': cl['url']
    }
    simplified_suspected_cls.append(simplified_cl)
  return simplified_suspected_cls


@ndb.transactional
def SaveAnalysisAfterHeuristicAnalysisCompletes(master_name, builder_name,
                                                build_number, build_completed,
                                                analysis_result, suspected_cls):
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  analysis.build_completed = build_completed
  analysis.result = analysis_result
  analysis.status = analysis_status.COMPLETED
  analysis.result_status = GetResultAnalysisStatus(analysis_result)
  analysis.suspected_cls = _GetSuspectedCLsWithOnlyCLInfo(suspected_cls)
  analysis.end_time = time_util.GetUTCNow()
  analysis.put()


def SaveSuspectedCLs(suspected_cls, master_name, builder_name, build_number,
                     current_failure_type):
  """Saves suspected CLs to dataStore."""
  for suspected_cl in suspected_cls:
    suspected_cl_util.UpdateSuspectedCL(
        suspected_cl['repo_name'], suspected_cl['revision'],
        suspected_cl['commit_position'], analysis_approach_type.HEURISTIC,
        master_name, builder_name, build_number, current_failure_type,
        suspected_cl['failures'], suspected_cl['top_score'])
