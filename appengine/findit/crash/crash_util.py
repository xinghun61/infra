# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict


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

  return total_same_parts >= (min(3, min(len(path_parts_1), len(path_parts_2))))
