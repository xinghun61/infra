# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the fake module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import inspect
import unittest

from services import cachemanager_svc
from services import config_svc
from services import features_svc
from services import issue_svc
from services import project_svc
from services import star_svc
from services import user_svc
from services import usergroup_svc
from testing import fake

fake_class_map = {
    fake.AbstractStarService: star_svc.AbstractStarService,
    fake.CacheManager: cachemanager_svc.CacheManager,
    fake.ProjectService: project_svc.ProjectService,
    fake.ConfigService: config_svc.ConfigService,
    fake.IssueService: issue_svc.IssueService,
    fake.UserGroupService: usergroup_svc.UserGroupService,
    fake.UserService: user_svc.UserService,
    fake.FeaturesService: features_svc.FeaturesService,
    }


class FakeMetaTest(unittest.TestCase):

  def testFunctionsHaveSameSignatures(self):
    """Verify that the fake class methods match the real ones."""
    for fake_cls, real_cls in fake_class_map.items():
      fake_attrs = set(dir(fake_cls))
      real_attrs = set(dir(real_cls))
      both_attrs = fake_attrs.intersection(real_attrs)
      to_test = [x for x in both_attrs if '__' not in x]
      for name in to_test:
        real_attr = getattr(real_cls, name)
        assert inspect.ismethod(real_attr)
        real_spec = inspect.getargspec(real_attr)
        fake_spec = inspect.getargspec(getattr(fake_cls, name))
        # check same number of args and kwargs
        real_kw_len = len(real_spec[3]) if real_spec[3] else 0
        fake_kw_len = len(fake_spec[3]) if fake_spec[3] else 0

        self.assertEquals(
            len(real_spec[0]) - real_kw_len,
            len(fake_spec[0]) - fake_kw_len,
            'Unequal number of args on %s.%s' % (fake_cls.__name__, name))
        self.assertEquals(
            real_kw_len, fake_kw_len,
            'Unequal number of kwargs on %s.%s' % (fake_cls.__name__, name))
        if real_kw_len:
          self.assertEquals(
              real_spec[0][-real_kw_len:],
              fake_spec[0][-fake_kw_len:],
              'Mismatched kwargs on %s.%s' % (fake_cls.__name__, name))
        self.assertEquals(
            real_spec[3], fake_spec[3],
            'Mismatched kwarg defaults on %s.%s' % (fake_cls.__name__, name))
