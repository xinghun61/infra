# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import os


class KeywordExtractor(object):
  """Extracts keywords from CrashReport.

  Returns a dict mapping keywords to their counts.
  """

  def __call__(self, crash_report):
    raise NotImplementedError()


class FilePathExtractor(KeywordExtractor):
  """Extracts file paths from crash_report.stacktrace.

  Note, for a frame, its file path is frame.dep_path + frame.file_path.
  """

  def __call__(self, crash_report):
    file_paths = defaultdict(int)
    for callstack in crash_report.stacktrace.stacks:
      for frame in callstack.frames:
        file_paths[os.path.join(frame.dep_path, frame.file_path)] += 1

    return dict(file_paths)
