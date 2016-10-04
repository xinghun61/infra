# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from crash import classifier
from crash.type_enums import CallStackLanguageType
from model.crash.crash_config import CrashConfig


class ProjectClassifier(classifier.Classifier):
  """Determines the project of a crash - (project_name, project_path).

  For example: ('chromium', 'src/'), ('skia', 'src/skia/'), ...etc.
  """

  def __init__(self):
    super(ProjectClassifier, self).__init__()
    self.project_classifier_config = CrashConfig.Get().project_classifier
    if self.project_classifier_config:
      self.project_classifier_config['host_directories'].sort(
          key=lambda host: -len(host.split('/')))

  def _GetProjectFromDepPath(self, dep_path):
    """Returns the project name from a dep path."""
    if not dep_path:
      return ''

    if dep_path == 'src/':
      return 'chromium'

    for host_directory in self.project_classifier_config['host_directories']:
      if dep_path.startswith(host_directory):
        path = dep_path[len(host_directory):]
        return 'chromium-%s' % path.split('/')[0].lower()

    # Unknown path, return the whole path as project name.
    return 'chromium-%s' % '_'.join(dep_path.split('/'))

  def GetClassFromStackFrame(self, frame):
    """Returns a tuple (project_name, project_path) of a StackFrame."""
    for marker, name in self.project_classifier_config[
        'function_marker_to_project_name'].iteritems():
      if frame.function.startswith(marker):
        return name

    for marker, name in self.project_classifier_config[
        'file_path_marker_to_project_name'].iteritems():
      if marker in frame.file_path or marker in frame.raw_file_path:
        return name

    return self._GetProjectFromDepPath(frame.dep_path)

  def GetClassFromResult(self, result):
    """Returns (project_name, project_path) of a Result."""
    if result.file_to_stack_infos:
      # A file in culprit result should always have its stack_info, namely a
      # list of (frame, callstack_priority) pairs.
      frame, _ = result.file_to_stack_infos.values()[0][0]
      return self.GetClassFromStackFrame(frame)

    return ''

  def Classify(self, results, crash_stack):
    """Classify project of a crash.

    Args:
      results (list of Result): culprit results.
      crash_stack (CallStack): the callstack that caused the crash.

    Returns:
      A tuple, project of the crash - (project_name, project_path).
    """
    if not self.project_classifier_config:
      logging.warning('Empty configuration for project classifier.')
      return ''

    def _GetRankFunction(language_type):
      if language_type == CallStackLanguageType.JAVA:
        def _RankFunctionForJava(occurrence):
          project_name = occurrence.name
          return (len(occurrence),
                  0 if 'chromium' in project_name else
                  self.project_classifier_config[
                      'non_chromium_project_rank_priority'][project_name])

        return _RankFunctionForJava

      return classifier.DefaultRankFunction

    # Set the max_classes to 1, so the returned projects only has one element.
    projects = self._Classify(
        results, crash_stack,
        self.project_classifier_config['top_n'], 1,
        rank_function=_GetRankFunction(crash_stack.language_type))

    if projects:
      return projects[0]

    return ''
