# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the warmup servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from testing import testing_helpers

from framework import sql
from framework import warmup
from services import service_manager


class WarmupTest(unittest.TestCase):

  def setUp(self):
    #self.cache_manager = cachemanager_svc.CacheManager()
    #self.services = service_manager.Services(
    #    cache_manager=self.cache_manager)
    self.services = service_manager.Services()
    self.servlet = warmup.Warmup(
        'req', 'res', services=self.services)


  def testHandleRequest_NothingToDo(self):
    mr = testing_helpers.MakeMonorailRequest()
    actual_json_data = self.servlet.HandleRequest(mr)
    self.assertEqual(
        {'success': 1},
        actual_json_data)
