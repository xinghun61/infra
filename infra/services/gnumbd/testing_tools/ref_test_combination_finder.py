#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Generate the list of all ref combinations which should be tested."""

from itertools import permutations as perm
from itertools import product as prod

ref_set = ['master', 'pending', 'tag']
ops_set = ['==', '>']

uniqs = set()
for refs in perm(ref_set, len(ref_set)):
  for o in prod(ops_set, repeat=2):
    cur_refs = list(refs)
    if o[0] == o[1] == '==':
      cur_refs = sorted(cur_refs)
    elif o[0] == '==':
      cur_refs[0:2] = sorted(cur_refs[0:2])
    elif o[1] == '==':
      cur_refs[1:] = sorted(cur_refs[1:])
    uniqs.add(' '.join((cur_refs[0], o[0], cur_refs[1], o[1], cur_refs[2])))

print '\n'.join(sorted(uniqs))
