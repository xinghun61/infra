# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.dict_of_basestring import DictOfBasestring
from model.wf_suspected_cl import WfSuspectedCL
from services import consistent_failure_culprits
from waterfall.test import wf_testcase


class ConsistentFailureCulpritsTest(wf_testcase.WaterfallTestCase):

  def testGetWfSuspectedClKeysFromCLInfo(self):
    cl_info = {
        'rev1': {
            'revision': 'rev1',
            'repo_name': 'chromium',
            'commit_position': 100
        },
        'rev2': {
            'revision': 'rev2',
            'repo_name': 'chromium',
            'commit_position': 123,
            'url': 'url'
        }
    }

    expected_cl_keys = {}
    for _, v in cl_info.iteritems():
      cl = WfSuspectedCL.Create(v['repo_name'], v['revision'],
                                v['commit_position'])
      cl.put()
      expected_cl_keys[v['revision']] = cl.key.urlsafe()

    self.assertEqual(expected_cl_keys,
                     consistent_failure_culprits.GetWfSuspectedClKeysFromCLInfo(
                         cl_info).ToSerializable())
