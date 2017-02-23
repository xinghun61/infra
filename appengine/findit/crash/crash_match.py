# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple


# TODO(wrengr): it's not clear why the ``priority`` is stored at all,
# given that every use in this file discards it. ``Result.file_to_stack_infos``
# should just store pointers directly to the frames themselves rather
# than needing this intermediate object.
# TODO(http://crbug.com/644476): this class needs a better name.
class FrameInfo(namedtuple('FrameInfo', ['frame', 'priority'])):
  """Represents a frame and information of the ``CallStack`` it belongs to."""

  __slots__ = ()

  def __str__(self):  # pragma: no cover
    return '%s(frame = %s, priority = %d)' % (
        self.__class__.__name__, str(self.frame), self.priority)


class CrashMatch(namedtuple('CrashMatch',
                            ['crashed_group', 'touched_files', 'frame_infos'])):

  """Represents a match between touched files with frames in stacktrace.

  The ``touched_files`` and ``frame_infos`` are matched under the same
  ``crashed_group``, for example, CrashedFile('file.cc') or
  CrashedDirectory('dir/').
  """
  __slots__ = ()

  def __str__(self):  # pragma: no cover
    return '%s(crashed_group = %s, touched_files = %s, frame_infos = %s)' % (
        self.__class__.__name__,
        self.crashed_group.value,
        ', '.join([str(touched_file) for touched_file in self.touched_files]),
        ', '.join([str(frame_info) for frame_info in self.frame_infos]))
