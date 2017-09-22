# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import os
import re

# Some projects like "chromium", have many sub projects like
# "chromium-blink", "chromium-skia", "chromium-pdfium"...etc., for those
# dep projects, the "chromium" ``Project`` can derive the names from their
# dep paths.
# Some other projects like "android_os", "clank", they don't have any dependency
# projects that are relavent to Predator.
_PROJECTS_WITH_DEP_PROJECTS = ['chromium']


# TODO(http://crbug.com/659346): write the coverage tests.
class Project(namedtuple('Project',
    ['name', 'path_regexes', 'function_regexes',
     'host_directories'])):
  """A representation of a "project", which may host many sub projects.

  For example: 'android_os', 'clank' or 'chromium'. Notably, a project knows
  how to identify itself. Hence, given a stack frame, file path or dependency
  path or whatever, we ask the ``Project``  whether it matches that frame,
  CL, etc.

  Properties:
    name (str): The name of the project, like "chromium", "android_os".
    path_regexes (list of re.RegexObject): Patterns of paths that project has.
    function_regexes (list of re.RegexObject): Patterns of functions that
      project has.
    host_directories (list of str): The root directories of this project and
      sub projects this project hosts.
      N.B. If ``host_directories`` is available, this project can match
      it with the passed-in ``dep_path`` to tell whether a suspect or stack is
      from this project. If this information is missing, the project cannot
      tell that from ``dep_path``; However, that doesn't mean the suspect or
      stack does not belong to this project, we can use other information like
      ``path_regexes`` or ``function_regexes`` to analyze.
  """
  __slots__ = ()

  def __new__(cls, name, path_regexes=None,
              function_regexes=None, host_directories=None):
    path_regexes = map(re.compile, path_regexes or [])
    function_regexes = map(re.compile, function_regexes or [])
    host_directories = host_directories or []

    return super(cls, Project).__new__(
        cls, name, path_regexes, function_regexes, host_directories)

  def MatchesStackFrame(self, frame):
    """Returns true if this project matches the frame."""
    # Sometimes some marker information are in the frame.raw_file_path.
    # An example, the path_regex for android_os is --
    # "https___googleplex-android.googlesource.com_a_platform_manifest.git/".
    # It can only be found in frame.raw_file_path, since the frame.file_path
    # has those kind of information stripped.
    for path_regex in self.path_regexes:
      if (frame.dep_path and frame.file_path and
          path_regex.match(os.path.join(frame.dep_path, frame.file_path))):
        return True

      if frame.raw_file_path and path_regex.match(frame.raw_file_path):
        return True

    if frame.function:
      for function_regex in self.function_regexes:
        if function_regex.match(frame.function):
          return True

    if frame.dep_path:
      for host_directory in self.host_directories:
        if frame.dep_path.startswith(host_directory):
          return True

    return False

  def MatchesTouchedFile(self, dep_path, file_path):
    """Returns true if this project matches the file path."""
    # If the path matches the path patterns.
    for path_regex in self.path_regexes:
      if path_regex.match(os.path.join(dep_path, file_path)):
        return True

    # If the dep_path hosted by this project.
    for host_directory in self.host_directories:
      if dep_path.startswith(host_directory):
        return True

    return False

  def GetName(self, dep_path=None):
    """Returns the project name based on dep path.

    N.B. (1) If this project doesn't have dep projects, just return the project
    name. (2) If this project does, return the derived dep project name based on
    the self.host_directories.
    """
    if self.name not in _PROJECTS_WITH_DEP_PROJECTS or dep_path is None:
      return self.name

    # For chromium project, get the name of the sub project from ``dep_path``.
    for host_directory in self.host_directories:
      if dep_path == host_directory:
        return self.name

      if dep_path.startswith(host_directory + '/'):
        path = dep_path[len(host_directory + '/'):].strip()
        return '%s-%s' % (self.name, path.split('/')[0].lower())

    # Unknown path, return the whole path as project name.
    return '%s-%s' % (self.name,
                      '_'.join([dep_part for dep_part in dep_path.split('/')
                                if dep_part]))
