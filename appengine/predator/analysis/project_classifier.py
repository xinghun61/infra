# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from analysis.occurrence import RankByOccurrence
from analysis.project import Project
from analysis.type_enums import LanguageType


class ProjectClassifier(object):
  """Determines the project of a crash - (project_name, project_path).

  For example: ('chromium', 'src/'), ('skia', 'src/skia/'), ...etc.
  """

  def __init__(self, projects, top_n_frames,
               non_chromium_project_rank_priority=None):
    super(ProjectClassifier, self).__init__()
    self.projects = projects
    self.top_n_frames = top_n_frames
    self.non_chromium_project_rank_priority = non_chromium_project_rank_priority

  @staticmethod
  def _GetTopProject(projects, rank_function=None):
    """Gets the highest ranking class among projects."""
    projects = RankByOccurrence(projects, 1, rank_function=rank_function)

    if projects:
      return projects[0]

    logging.warning('ProjectClassifier.Classify: no projects found.')
    return None

  def ClassifyCallStack(self, crash_stack):
    """Determines which project is responsible for this crash stack.

    Args:
      crash_stack (CallStack): The crash_stack of the Stacktrace for this crash.

    Returns:
      The name of the most-suspected project; or the empty string on failure.
    """
    rank_function = None
    if crash_stack.language_type == LanguageType.JAVA:
      def RankFunctionForJava(occurrence):
        if 'chromium' in occurrence.name:
          index = 0
        else:
          index = self.non_chromium_project_rank_priority[occurrence.name]
        return -len(occurrence), index

      rank_function = RankFunctionForJava

    def GetProjectFromStackFrame(frame):
      """Determine which project is responsible for this frame."""
      for project in self.projects:
        if project.MatchesStackFrame(frame):
          return project.GetName(frame.dep_path)

      return None

    projects = map(GetProjectFromStackFrame,
                   crash_stack.frames[:self.top_n_frames])

    return ProjectClassifier._GetTopProject(projects,
                                            rank_function=rank_function)

  def ClassifySuspect(self, suspect):
    """Determine which project is responsible for this suspect."""
    if not suspect or not suspect.changelog:
      return None

    def GetProjectFromTouchedFile(touched_file):
      for project in self.projects:
        if project.MatchesTouchedFile(suspect.dep_path,
                                      touched_file.changed_path):
          return project.GetName(suspect.dep_path)

      return None

    projects = map(GetProjectFromTouchedFile, suspect.changelog.touched_files)
    return ProjectClassifier._GetTopProject(projects,
                                            rank_function=lambda x:-len(x))

  def ClassifySuspects(self, suspects):
    """Determines which project is resposible for these suspects.

    Args:
      suspects (list of Suspect): culprit suspects.

    Returns:
      The name of the most-suspected project; or the empty string on failure.
    """
    projects = map(self.ClassifySuspect, suspects)
    return ProjectClassifier._GetTopProject(projects,
                                            rank_function=lambda x:-len(x))
