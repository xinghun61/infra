# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities for translating between entity-specifics and dtos for waterfall."""

from dto.dict_of_basestring import DictOfBasestring
from model.wf_suspected_cl import WfSuspectedCL


def GetWfSuspectedClKeysFromCLInfo(cl_info):
  """Get a dict of urlsafe keys object from result of GetCLInfo."""
  cl_keys = DictOfBasestring()
  for revision, info in cl_info.iteritems():
    culprit = WfSuspectedCL.Get(info['repo_name'], info['revision'])
    if not culprit:
      continue
    cl_keys[revision] = culprit.key.urlsafe()
  return cl_keys
