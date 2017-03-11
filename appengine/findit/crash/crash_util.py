# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from crash.crash_match import CrashMatch
from crash.crash_match import FrameInfo


def IsSameFilePath(path_1, path_2):
  """Determines if two paths represent same path.

  First we split each path into a list of directories (via split('/')),
  then we treat those lists as multisets (i.e., ignore the order of
  directories, but keep track of their multiplicities) and take the
  multiset intersection. Finally, we return whether the number of elements
  in the intersection is at least 3 (or, when one of the paths has
  fewer than 3 parts, we return whether all those parts are also in the
  other path)

  Args:
    path_1 (str): First path.
    path_2 (str): Second path to compare.

  Returns:
    Boolean, True if it they are thought to be a same path, False otherwise.
  """
  if not path_1 and not path_2:
    return True

  if not path_1 or not path_2:
    return False

  # TODO(katesonia): Think of better way to determine whether 2 paths are the
  # same or not.
  path_parts_1 = path_1.lower().split('/')
  path_parts_2 = path_2.lower().split('/')

  if path_parts_1[-1] != path_parts_2[-1]:
    return False

  def _GetPathPartsCount(path_parts):
    path_parts_count = defaultdict(int)

    for path_part in path_parts:
      path_parts_count[path_part] += 1

    return path_parts_count

  parts_count_1 = _GetPathPartsCount(path_parts_1)
  parts_count_2 = _GetPathPartsCount(path_parts_2)

  # Get number of same path parts between path_1 and path_2. For example:
  # a/b/b/b/f.cc and a/b/b/c/d/f.cc have 4 path parts the same in total.
  total_same_parts = sum([min(parts_count_1[part], parts_count_2[part]) for
                          part in parts_count_1 if part in path_parts_2])

  return total_same_parts >= min(3, min(len(path_parts_1), len(path_parts_2)))


def IndexFramesWithCrashedGroup(stacktrace, crashed_group_factory,
                                dependencies):
  """Index frames in stacktrace by dep_path and crashed_groups.

  Args:
    stacktrace (Stacktrace): The stacktrace to parse.
    crashed_group_factory (callable): A callable to factory crashed_group.
      N.B. So as to be used a key in a dict, the ``crashed_group`` should be
      able to be hashed.
    dependencies (dict of Dependency): Dict mapping dep path to ``Dependency``s.
      The ``dependencies`` is used to filter those frames whose dep path are
      not in ``dependencies``.

  Returns:
    A dict mapping dep_path to crashed_group to list of ``FrameInfo``s.
    For example:
    {
        'src/': {
            'a.cc': [
                FrameInfo(StackFrame(0, 'src/', '', 'func', 'a.cc', [1]), 0),
                FrameInfo(StackFrame(2, 'src/', '', 'func', 'a.cc', [33]), 0),
            ]
        }
    }
  """
  frame_infos = defaultdict(lambda: defaultdict(list))

  for stack in stacktrace.stacks:
    for frame in stack.frames:
      if frame.dep_path not in dependencies:
        continue

      crashed_group = crashed_group_factory(frame)
      if crashed_group:
        frame_infos[frame.dep_path][crashed_group].append(
            FrameInfo(frame, stack.priority))

  return frame_infos


def MatchSuspectWithFrameInfos(suspect, grouped_frame_infos, match_func):
  """Matches touched files of suspect with frames in stacktrace.

  Args:
    suspect (Suspect): The suspect to match with frames.
    grouped_frame_infos (dict of FrameInfo):  Dict mapping a crashed group (
      For example, CrashedFile('f.cc'), CrashedDirectory('dir/').

  Returns:
    A dict mapping crashed group to a ``CrashMatch``.
  """

  # Dict mapping files in stacktrace touched by suspect to there
  # corresponding stacktrace frames information.
  matched_touched_files = defaultdict(list)
  for crashed in grouped_frame_infos:
    for touched_file in suspect.changelog.touched_files:
      if match_func(crashed, touched_file):
        matched_touched_files[crashed].append(touched_file)

  return {crashed: CrashMatch(crashed_group=crashed,
                              touched_files=matched_touched_files[crashed],
                              frame_infos=grouped_frame_infos[crashed])
          for crashed in matched_touched_files}
