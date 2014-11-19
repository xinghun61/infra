# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import itertools
import os.path

# pylint: disable=C0301
# http://stackoverflow.com/questions/9470611/how-to-do-an-inverse-range-i-e-create-a-compact-range-based-on-a-set-of-numb/9471386#9471386


def re_range(lst):
  def sub(x):
    return x[1] - x[0]

  ranges = []
  for _, iterable in itertools.groupby(enumerate(sorted(lst)), sub):
    rng = list(iterable)
    if len(rng) == 1:
      s = str(rng[0][1])
    else:
      s = '%s-%s' % (rng[0][1], rng[-1][1])
    ranges.append(s)
  return ', '.join(ranges)


# We used to have our own implementation here, but it turns out
# python has one, just burried inside os.path!?
def longest_substring(string1, string2):
  return os.path.commonprefix([string1, string2])
