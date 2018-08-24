# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE files.
"""Provides functions to analyze build failures.

It has functions to:
  * Provide common logic to help analyze build failures.
"""

import logging
import os
from collections import defaultdict

from google.appengine.ext import ndb

from common import monitoring
from common.constants import NO_BLAME_ACTION_ACCOUNTS
from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import analysis_status
from libs import time_util
from libs.gitiles.diff import ChangeType
from libs.list_of_basestring import ListOfBasestring
from model import analysis_approach_type
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_suspected_cl import WfSuspectedCL
from services import files
from services import git
from waterfall import suspected_cl_util
from waterfall.failure_signal import FailureSignal


def _GetChangedLinesForChromiumRepo(repo_info, touched_file, line_numbers,
                                    suspected_revision):
  """Checks if the CL made change close to the failed line in log.

  Args:
    repo_info (dict): The repo_url and revision for the build cycle.
    touched_file (FileChangeInfo): The touched file found in the change log.
    line_numbers (list): List of line_numbers mentioned in the failure log.
    suspected_revision (str): Git hash revision of the suspected CL.

  Returns:
    A list of lines which are mentioned in log and changed in cl.
  """
  changed_line_numbers = []
  if line_numbers and repo_info:
    blame = git.GetGitBlame(repo_info['repo_url'], repo_info['revision'],
                            touched_file.new_path)
    if blame:
      for line_number in line_numbers:
        for region in blame:
          if (region.revision == suspected_revision and
              (line_number >= region.start and
               line_number <= region.start + region.count - 1)):
            changed_line_numbers.append(line_number)

  return changed_line_numbers


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
            change_action, changed_src_file_path, ', '.join(
                map(str, changed_line_numbers)))
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
      hint = (
          '%s dependency %s with changes in %s '
          '(and %s(added) was in log)' %
          (change_action, dep_path, url_to_changes_in_roll, file_path_in_log))
    elif roll_file_change_type == ChangeType.DELETE:
      hint = (
          '%s dependency %s with changes in %s '
          '(and %s(deleted) was in log)' %
          (change_action, dep_path, url_to_changes_in_roll, file_path_in_log))
    elif changed_line_numbers:
      hint = ('%s dependency %s with changes in %s (and %s[%s] was in log)' %
              (change_action, dep_path, url_to_changes_in_roll,
               file_path_in_log, ', '.join(map(str, changed_line_numbers))))
    else:
      hint = ('%s dependency %s with changes in %s (and %s was in log)' % (
          change_action, dep_path, url_to_changes_in_roll, file_path_in_log))

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
    touched_file (FileChangeInfo): The touched file found in the change log.
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
  change_type = touched_file.change_type

  if change_type == ChangeType.MODIFY:
    changed_src_file_path = touched_file.new_path
    file_name = os.path.basename(changed_src_file_path)

    score = 0
    changed_line_numbers = None
    if files.IsSameFile(changed_src_file_path, file_path_in_log):
      changed_line_numbers = _GetChangedLinesForChromiumRepo(
          repo_info, touched_file, line_numbers, suspected_revision)
      if changed_line_numbers:
        score = 4
      else:
        score = 2
    elif files.IsRelated(changed_src_file_path, file_path_in_log):
      score = 1

    if score:
      justification.AddFileChange('modified', changed_src_file_path,
                                  file_path_in_log, score,
                                  file_name_occurrences.get(file_name),
                                  changed_line_numbers, check_dependencies)

  if change_type in (ChangeType.ADD, ChangeType.COPY, ChangeType.RENAME):
    changed_src_file_path = touched_file.new_path
    file_name = os.path.basename(changed_src_file_path)

    score = 0
    if files.IsSameFile(changed_src_file_path, file_path_in_log):
      score = 5
    elif files.IsRelated(changed_src_file_path, file_path_in_log):
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
    changed_src_file_path = touched_file.old_path
    file_name = os.path.basename(changed_src_file_path)

    score = 0
    if files.IsSameFile(changed_src_file_path, file_path_in_log):
      score = 5
    elif files.IsRelated(changed_src_file_path, file_path_in_log):
      score = 1

    if score:
      justification.AddFileChange(
          'deleted',
          changed_src_file_path,
          file_path_in_log,
          score,
          file_name_occurrences.get(file_name),
          check_dependencies=check_dependencies)


def _GetChangeTypeAndCulpritCommit(file_path_in_log, changes_between_revisions):
  """Determines the first commit that touches a file within a revision range.

  Args:
    file_path_in_log: The file to search each commit's change logs for.
    changes_between_revisions: A list of ChangeLogs.

  Returns:
    The modification type made to file_path_in_log if found.
    The corresponding commit that touched file_path_in_log if found.
  """

  for change_log in changes_between_revisions:
    # Use the change log for each commit to determine if and how
    # file_path_in_log log was modified.
    for file_change_info in change_log.touched_files:
      if file_change_info.change_type in (ChangeType.DELETE, ChangeType.RENAME):
        changed_src_file_path = file_change_info.old_path
      else:
        changed_src_file_path = file_change_info.new_path

      if files.IsSameFile(changed_src_file_path, file_path_in_log):
        # Found the file and the commit that modified it.
        # TODO(lijeffrey): It is possible multiple commits modified the files.
        return file_change_info.change_type, change_log.revision

      # TODO(lijeffrey): It is possible files.IsRelated(changed_src_file_path,
      # file_path_in_log) may also provide useful information, but how is not
      # yet determined.

  return None, None


def _GetChangedLinesForDependencyRepo(roll, file_path_in_log, line_numbers):
  """Gets changed line numbers for file in failure log.

    Tests if the same lines mentioned in failure log are changed within
    the DEPS roll, if so, return those line numbers.
  """
  roll_repo = CachedGitilesRepository(FinditHttpClient(), roll['repo_url'])
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

  changes_in_roll = roll_repo.GetChangeLogs(old_revision, new_revision)
  file_change_type, culprit_commit = _GetChangeTypeAndCulpritCommit(
      file_path_in_log, changes_in_roll)

  if culprit_commit is None:
    # Bail out if no commits touched the file in the log.
    return file_change_type, changed_line_numbers

  if file_change_type == ChangeType.MODIFY:
    # If the file was modified, use the blame information to determine which
    # lines were changed.
    blame = roll_repo.GetBlame(file_path_in_log, culprit_commit)

    if not blame:
      return file_change_type, changed_line_numbers

    revisions_in_roll = [change.revision for change in changes_in_roll]
    for region in blame:
      if line_numbers:
        for line_number in line_numbers:
          if (line_number >= region.start and
              line_number <= region.start + region.count - 1 and
              region.revision in revisions_in_roll):
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
    if roll['path'] == 'src/v8':
      # Cannot compare author time for v8 roll, author time for CLs during the
      # roll may be earlier than the author time of old revision.
      # TODO: Figure out the rolling mechanism of v8 to add logic for checking
      # this repo.
      continue

    change_action = None
    dep_path = files.StripChromiumRootDirectory(roll['path'])
    if not file_path_in_log.startswith(dep_path + '/'):
      continue

    changed_lines = []
    roll_file_change_type = None
    if roll['old_revision'] and roll['new_revision']:
      roll_file_change_type, changed_lines = _GetChangedLinesForDependencyRepo(
          roll, file_path_in_log[len(dep_path + '/'):], line_numbers)

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
                              file_path_in_log[len(dep_path + '/'):], score,
                              changed_lines, roll_file_change_type)


def CheckFiles(failure_signal, change_log, deps_info, check_dependencies=False):
  """Checks files in the given change log of a CL against the failure signal.

  Args:
    failure_signal (FailureSignal): The failure signal of a failed step or test.
    change_log (ChangeLog): The change log of a CL.
    deps_info (dict): Output of pipeline ExtractDEPSInfoPipeline.
    check_dependencies (bool): If it's true check ninja dependencies.

  Returns:
    A dict as returned by _Justification.ToDict() if the CL is suspected for the
    failure; otherwise None.
  """
  # Use a dict to map each file name of the touched files to their occurrences.
  file_name_occurrences = defaultdict(int)
  for touched_file in change_log.touched_files:
    change_type = touched_file.change_type
    if (change_type in (ChangeType.ADD, ChangeType.COPY, ChangeType.RENAME,
                        ChangeType.MODIFY)):
      file_name = os.path.basename(touched_file.new_path)
      file_name_occurrences[file_name] += 1

    if change_type in (ChangeType.DELETE, ChangeType.RENAME):
      file_name = os.path.basename(touched_file.old_path)
      file_name_occurrences[file_name] += 1

  justification = _Justification()

  rolls = deps_info.get('deps_rolls', {}).get(change_log.revision, [])
  repo_info = deps_info.get('deps', {}).get('src', {})

  if not check_dependencies:
    for file_path_in_log, line_numbers in failure_signal.files.iteritems():
      file_path_in_log = files.StripChromiumRootDirectory(file_path_in_log)

      for touched_file in change_log.touched_files:
        _CheckFile(touched_file, file_path_in_log, justification,
                   file_name_occurrences, line_numbers, repo_info,
                   change_log.revision)

      _CheckFileInDependencyRolls(file_path_in_log, rolls, justification,
                                  line_numbers)
  else:
    for failed_edge in failure_signal.failed_edges:
      for dependency in failed_edge.get('dependencies'):
        dependency = files.StripChromiumRootDirectory(dependency)
        for touched_file in change_log.touched_files:
          _CheckFile(touched_file, dependency, justification,
                     file_name_occurrences, None, repo_info,
                     change_log.revision, True)

        _CheckFileInDependencyRolls(dependency, rolls, justification, [])
  if not justification.score:
    return None
  return justification.ToDict()


class CLInfo(object):
  """A object of information we need for a suspected CL.

  The information is specific to current build.
  """

  def __init__(self):
    self.failures = defaultdict(list)
    self.top_score = 0
    self.url = None


def SaveFailureToMap(cl_failure_map, new_suspected_cl_dict, step_name,
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
  cl_failure_map[cl_key].top_score = (
      cl_failure_map[cl_key].top_score or top_score)
  cl_failure_map[cl_key].url = (
      cl_failure_map[cl_key].url or new_suspected_cl_dict['url'])


def ConvertCLFailureMapToList(cl_failure_map):
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


def CreateCLInfoDict(justification_dict, build_number, change_log):
  # TODO(stgao): remove hard-coded 'chromium' when DEPS file parsing is
  # supported.
  cl_info = {
      'build_number': build_number,
      'repo_name': 'chromium',
      'revision': change_log.revision,
      'commit_position': change_log.commit_position,
      'url': change_log.code_review_url or change_log.commit_url,
  }

  cl_info.update(justification_dict)
  return cl_info


def GetLowerBoundForAnalysis(step_failure_info):
  return (step_failure_info.last_pass + 1
          if step_failure_info.last_pass else step_failure_info.first_failure)


def InitializeStepLevelResult(step_name, step_failure_info):
  return {
      'step_name': step_name,
      'first_failure': step_failure_info.first_failure,
      'last_pass': step_failure_info.last_pass,
      'suspected_cls': [],
      'supported': step_failure_info.supported
  }


def AnalyzeOneCL(build_number,
                 failure_signal,
                 change_log,
                 deps_info,
                 use_ninja_output=False):
  """Checks one CL to see if it's a suspect."""

  if change_log and change_log.author.email in NO_BLAME_ACTION_ACCOUNTS:
    # This change should never be flagged as suspect.
    justification_dict = None
  else:
    justification_dict = CheckFiles(failure_signal, change_log, deps_info,
                                    use_ninja_output)

  if not justification_dict:
    return None, None

  return (CreateCLInfoDict(justification_dict, build_number, change_log),
          max(justification_dict['hints'].values()))


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

  duration = analysis.end_time - analysis.start_time
  status = result_status.RESULT_STATUS_TO_DESCRIPTION.get(
      analysis.result_status, 'no result')
  monitoring.analysis_durations.add(
      duration.total_seconds(), {
          'type':
              failure_type.GetDescriptionForFailureType(analysis.failure_type),
          'result':
              'heuristic-' + status,
      })


def SaveSuspectedCLs(suspected_cls, master_name, builder_name, build_number,
                     current_failure_type):
  """Saves suspected CLs to dataStore."""
  for suspected_cl in suspected_cls:
    suspected_cl_util.UpdateSuspectedCL(
        suspected_cl['repo_name'], suspected_cl['revision'],
        suspected_cl['commit_position'], analysis_approach_type.HEURISTIC,
        master_name, builder_name, build_number, current_failure_type,
        suspected_cl['failures'], suspected_cl['top_score'])


def GetHeuristicSuspectedCLs(master_name, builder_name, build_number):
  """Gets revisions of suspected cls found by heuristic approach."""
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  suspects = ListOfBasestring()
  if analysis and analysis.suspected_cls:
    for cl in analysis.suspected_cls:
      culprit = WfSuspectedCL.Get(cl['repo_name'], cl['revision'])
      if not culprit:  # pragma: no cover
        logging.warning('No culprit found for repo_name %s and revision %s',
                        cl['repo_name'], cl['revision'])
        continue
      suspects.append(culprit.key.urlsafe())

  return suspects


def ResetAnalysisForANewAnalysis(master_name, builder_name, build_number,
                                 pipeline_status_path, current_version):
  """Resets the WfAnalysis object to start a new analysis."""
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  analysis.Reset(
      pipeline_status_path=pipeline_status_path,
      status=analysis_status.RUNNING,
      analysis_result_status=None,
      start_time=time_util.GetUTCNow(),
      end_time=None,
      version=current_version)


def UpdateAbortedAnalysis(parameters):
  """Updates analysis and checks if there is enough information to run a try job
   even if analysis aborts.

  Args:
    parameters(AnalyzeCompileFailureInput): Inputs to analyze a compile failure.

  Returns:
    (WfAnalysis, bool): WfAnalysis object and a bool value indicates if can
      resume the try job or not.
  """
  master_name, builder_name, build_number = parameters.build_key.GetParts()
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  assert analysis, ('WfAnalysis Object for {}/{}/{} was missing'.format(
      master_name, builder_name, build_number))

  # Heuristic analysis could have already completed, while triggering the
  # try job kept failing and lead to the abort.
  run_try_job = False
  heuristic_aborted = False
  if not analysis.completed:
    # Heuristic analysis is aborted.
    analysis.status = analysis_status.ERROR
    analysis.result_status = None
    heuristic_aborted = True

    if analysis.failure_info:
      # We need failure_info to run try jobs,
      # while signals is optional for compile try jobs.
      run_try_job = True
  analysis.aborted = True
  analysis.put()
  return analysis, run_try_job, heuristic_aborted
