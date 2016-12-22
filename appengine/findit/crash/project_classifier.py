# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from crash.occurrence import RankByOccurrence
from crash.type_enums import LanguageType
from model.crash.crash_config import CrashConfig


class ProjectClassifier(object):
  """Determines the project of a crash - (project_name, project_path).

  For example: ('chromium', 'src/'), ('skia', 'src/skia/'), ...etc.
  """

  # TODO(http://crbug.com/657177): remove dependency on CrashConfig.
  def __init__(self):
    super(ProjectClassifier, self).__init__()
    self.project_classifier_config = CrashConfig.Get().project_classifier
    if self.project_classifier_config:
      self.project_classifier_config['host_directories'].sort(
          key=lambda host: -len(host.split('/')))

  # TODO(http://crbug.com/657177): refactor this into a method on Project.
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

  # TODO(http://crbug.com/657177): refactor this into Project.MatchesStackFrame.
  def GetClassFromStackFrame(self, frame):
    """Determine which project is responsible for this frame."""
    for marker, name in self.project_classifier_config[
        'function_marker_to_project_name'].iteritems():
      if frame.function.startswith(marker):
        return name

    for marker, name in self.project_classifier_config[
        'file_path_marker_to_project_name'].iteritems():
      if marker in frame.file_path or marker in frame.raw_file_path:
        return name

    return self._GetProjectFromDepPath(frame.dep_path)

  # TODO(wrengr): refactor this into a method on Suspect which returns
  # the cannonical frame (and documents why it's the one we return).
  def GetClassFromSuspect(self, suspect):
    """Determine which project is responsible for this suspect."""
    if suspect.file_to_stack_infos:
      # file_to_stack_infos is a dict mapping file_path to stack_infos,
      # where stack_infos is a list of (frame, callstack_priority)
      # pairs. So ``.values()`` returns a list of the stack_infos in an
      # arbitrary order; the first ``[0]`` grabs the "first" stack_infos;
      # the second ``[0]`` grabs the first pair from the list; and
      # the third ``[0]`` grabs the ``frame`` from the pair.
      # TODO(wrengr): why is that the right frame to look at?
      frame = suspect.file_to_stack_infos.values()[0][0][0]
      return self.GetClassFromStackFrame(frame)

    return ''

  def Classify(self, suspects, crash_stack):
    """Classify project of a crash.

    Args:
      suspects (list of Suspect): culprit suspects.
      crash_stack (CallStack): the callstack that caused the crash.

    Returns:
      The name of the most-suspected project; or the empty string on failure.
    """
    if not self.project_classifier_config:
      logging.warning('ProjectClassifier.Classify: Empty configuration.')
      return None

    rank_function = None
    if crash_stack.language_type == LanguageType.JAVA:
      def _RankFunctionForJava(occurrence):
        # TODO(wrengr): why are we weighting by the length, instead of
        # the negative length as we do in the DefaultOccurrenceRanging?
        weight = len(occurrence)
        project_name = occurrence.name
        if 'chromium' in project_name:
          index = 0
        else:
          index = self.project_classifier_config[
              'non_chromium_project_rank_priority'][project_name]
        return (weight, index)

      rank_function = _RankFunctionForJava

    top_n_frames = self.project_classifier_config['top_n']
    # If ``suspects`` are available, we use the projects from there since
    # they're more reliable than the ones from the ``crash_stack``.
    if suspects:
      classes = map(self.GetClassFromSuspect, suspects[:top_n_frames])
    else:
      classes = map(self.GetClassFromStackFrame,
          crash_stack.frames[:top_n_frames])

    # Since we're only going to return the highest-ranked class, might
    # as well set ``max_classes`` to 1.
    projects = RankByOccurrence(classes, 1, rank_function=rank_function)

    if projects:
      return projects[0]

    logging.warning('ProjectClassifier.Classify: no projects found.')
    return ''
