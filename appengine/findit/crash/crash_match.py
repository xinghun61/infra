# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from collections import defaultdict
from collections import namedtuple


class CrashedGroup(namedtuple('CrashedGroup', ['value'])):
  """Represents a crashed group.

  Properties:
    value (str): The content of crashed group, for example, 'crashed_file_name',
      'crashed_directory'.
    name (str): The class name of the crashed group. It is mainly used by
      sub classes to return the their class names, for example,
      'CrashedComponent', 'CrashedDirectory'.
  """
  __slots__ = ()

  @property
  def name(self):  # pragma: no cover
    return self.__class__.__name__


# TODO(wrengr): it's not clear why the ``priority`` is stored at all,
# given that every use in this file discards it. ``Result.file_to_stack_infos``
# should just store pointers directly to the frames themselves rather
# than needing this intermediate object.
# TODO(http://crbug.com/644476): this class needs a better name.
class FrameInfo(namedtuple('FrameInfo', ['frame', 'priority'])):
  """Represents a frame and information of the ``CallStack`` it belongs to."""

  __slots__ = ()


class CrashMatch(namedtuple('CrashMatch',
                            ['crashed_group', 'touched_files', 'frame_infos'])):

  """Represents a match between touched files with frames in stacktrace.

  The ``touched_files`` and ``frame_infos`` are matched under the same
  ``crashed_group``, for example, CrashedFile('file.cc') or
  CrashedDirectory('dir/').
  """
  __slots__ = ()

  def __str__(self):  # pragma: no cover
    frame_file_path_to_index = defaultdict(list)
    for frame_info in self.frame_infos:
      frame_file_path_to_index[
          frame_info.frame.file_path].append(frame_info.frame.index)

    frame_file_path_to_index = {
        file_path: ', '.join(['frame#%d' % indice for indice in index])
        for file_path, index in frame_file_path_to_index.iteritems()
    }
    return 'Changed files %s, with the same %s(%s) as %s' % (
        ', '.join([os.path.basename(f.new_path) for f in self.touched_files]),
        self.crashed_group.name, self.crashed_group.value,
        ', '.join(['%s (in %s)' % (os.path.basename(path), index)
                   for path, index in frame_file_path_to_index.iteritems()]))
