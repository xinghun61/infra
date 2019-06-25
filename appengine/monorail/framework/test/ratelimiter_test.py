# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for RateLimiter.
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import unittest

from google.appengine.api import memcache
from google.appengine.ext import testbed

import mox
import os
import settings

from framework import ratelimiter
from services import service_manager
from services import client_config_svc
from testing import fake
from testing import testing_helpers


class RateLimiterTest(unittest.TestCase):
  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_user_stub()

    self.mox = mox.Mox()
    self.services = service_manager.Services(
      config=fake.ConfigService(),
      issue=fake.IssueService(),
      user=fake.UserService(),
      project=fake.ProjectService(),
    )
    self.project = self.services.project.TestAddProject('proj', project_id=987)

    self.ratelimiter = ratelimiter.RateLimiter()
    ratelimiter.COUNTRY_LIMITS = {}
    os.environ['USER_EMAIL'] = ''
    settings.ratelimiting_enabled = True
    ratelimiter.DEFAULT_LIMIT = 10

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()
    # settings.ratelimiting_enabled = True

  def testCheckStart_pass(self):
    request, _ = testing_helpers.GetRequestObjects(
      project=self.project)
    request.headers['X-AppEngine-Country'] = 'US'
    request.remote_addr = '192.168.1.0'
    self.ratelimiter.CheckStart(request)
    # Should not throw an exception.

  def testCheckStart_fail(self):
    request, _ = testing_helpers.GetRequestObjects(
      project=self.project)
    request.headers['X-AppEngine-Country'] = 'US'
    request.remote_addr = '192.168.1.0'
    now = 0.0
    cachekeysets, _, _, _ = ratelimiter._CacheKeys(request, now)
    values = [{key: ratelimiter.DEFAULT_LIMIT for key in cachekeys} for
              cachekeys in cachekeysets]
    for value in values:
      memcache.add_multi(value)
    with self.assertRaises(ratelimiter.RateLimitExceeded):
      self.ratelimiter.CheckStart(request, now)

  def testCheckStart_expiredEntries(self):
    request, _ = testing_helpers.GetRequestObjects(
      project=self.project)
    request.headers['X-AppEngine-Country'] = 'US'
    request.remote_addr = '192.168.1.0'
    now = 0.0
    cachekeysets, _, _, _ = ratelimiter._CacheKeys(request, now)
    values = [{key: ratelimiter.DEFAULT_LIMIT for key in cachekeys} for
              cachekeys in cachekeysets]
    for value in values:
      memcache.add_multi(value)

    now = now + 2 * ratelimiter.EXPIRE_AFTER_SECS
    self.ratelimiter.CheckStart(request, now)
    # Should not throw an exception.

  def testCheckStart_repeatedCalls(self):
    request, _ = testing_helpers.GetRequestObjects(
      project=self.project)
    request.headers['X-AppEngine-Country'] = 'US'
    request.remote_addr = '192.168.1.0'
    now = 0.0

    # Call CheckStart once every minute.  Should be ok.
    for _ in range(ratelimiter.N_MINUTES):
      self.ratelimiter.CheckStart(request, now)
      now = now + 120.0

    # Call CheckStart more than DEFAULT_LIMIT times in the same minute.
    with self.assertRaises(ratelimiter.RateLimitExceeded):
      for _ in range(ratelimiter.DEFAULT_LIMIT + 2):  # pragma: no branch
        now = now + 0.001
        self.ratelimiter.CheckStart(request, now)

  def testCheckStart_differentIPs(self):
    now = 0.0

    ratelimiter.COUNTRY_LIMITS = {}
    # Exceed DEFAULT_LIMIT calls, but vary remote_addr so different
    # remote addresses aren't ratelimited together.
    for m in range(ratelimiter.DEFAULT_LIMIT * 2):
      request, _ = testing_helpers.GetRequestObjects(
        project=self.project)
      request.headers['X-AppEngine-Country'] = 'US'
      request.remote_addr = '192.168.1.%d' % (m % 16)
      ratelimiter._CacheKeys(request, now)
      self.ratelimiter.CheckStart(request, now)
      now = now + 0.001

    # Exceed the limit, but only for one IP address. The
    # others should be fine.
    with self.assertRaises(ratelimiter.RateLimitExceeded):
      for m in range(ratelimiter.DEFAULT_LIMIT):  # pragma: no branch
        request, _ = testing_helpers.GetRequestObjects(
          project=self.project)
        request.headers['X-AppEngine-Country'] = 'US'
        request.remote_addr = '192.168.1.0'
        ratelimiter._CacheKeys(request, now)
        self.ratelimiter.CheckStart(request, now)
        now = now + 0.001

    # Now proceed to make requests for all of the other IP
    # addresses besides .0.
    for m in range(ratelimiter.DEFAULT_LIMIT * 2):
      request, _ = testing_helpers.GetRequestObjects(
        project=self.project)
      request.headers['X-AppEngine-Country'] = 'US'
      # Skip .0 since it's already exceeded the limit.
      request.remote_addr = '192.168.1.%d' % (m + 1)
      ratelimiter._CacheKeys(request, now)
      self.ratelimiter.CheckStart(request, now)
      now = now + 0.001

  def testCheckStart_sameIPDifferentUserIDs(self):
    # Behind a NAT, e.g.
    now = 0.0

    # Exceed DEFAULT_LIMIT calls, but vary user_id so different
    # users behind the same IP aren't ratelimited together.
    for m in range(ratelimiter.DEFAULT_LIMIT * 2):
      request, _ = testing_helpers.GetRequestObjects(
        project=self.project)
      request.remote_addr = '192.168.1.0'
      os.environ['USER_EMAIL'] = '%s@example.com' % m
      request.headers['X-AppEngine-Country'] = 'US'
      ratelimiter._CacheKeys(request, now)
      self.ratelimiter.CheckStart(request, now)
      now = now + 0.001

    # Exceed the limit, but only for one userID+IP address. The
    # others should be fine.
    with self.assertRaises(ratelimiter.RateLimitExceeded):
      for m in range(ratelimiter.DEFAULT_LIMIT + 2):  # pragma: no branch
        request, _ = testing_helpers.GetRequestObjects(
          project=self.project)
        request.headers['X-AppEngine-Country'] = 'US'
        request.remote_addr = '192.168.1.0'
        os.environ['USER_EMAIL'] = '42@example.com'
        ratelimiter._CacheKeys(request, now)
        self.ratelimiter.CheckStart(request, now)
        now = now + 0.001

    # Now proceed to make requests for other user IDs
    # besides 42.
    for m in range(ratelimiter.DEFAULT_LIMIT * 2):
      request, _ = testing_helpers.GetRequestObjects(
        project=self.project)
      request.headers['X-AppEngine-Country'] = 'US'
      # Skip .0 since it's already exceeded the limit.
      request.remote_addr = '192.168.1.0'
      os.environ['USER_EMAIL'] = '%s@example.com' % (43 + m)
      ratelimiter._CacheKeys(request, now)
      self.ratelimiter.CheckStart(request, now)
      now = now + 0.001

  def testCheckStart_ratelimitingDisabled(self):
    settings.ratelimiting_enabled = False
    request, _ = testing_helpers.GetRequestObjects(
      project=self.project)
    request.headers['X-AppEngine-Country'] = 'US'
    request.remote_addr = '192.168.1.0'
    now = 0.0

    # Call CheckStart a lot.  Should be ok.
    for _ in range(ratelimiter.DEFAULT_LIMIT):
      self.ratelimiter.CheckStart(request, now)
      now = now + 0.001

  def testCheckStart_perCountryLoggedOutLimit(self):
    ratelimiter.COUNTRY_LIMITS['US'] = 10

    request, _ = testing_helpers.GetRequestObjects(
      project=self.project)
    request.headers[ratelimiter.COUNTRY_HEADER] = 'US'
    request.remote_addr = '192.168.1.1'
    now = 0.0

    with self.assertRaises(ratelimiter.RateLimitExceeded):
      for m in range(ratelimiter.DEFAULT_LIMIT + 2):  # pragma: no branch
        self.ratelimiter.CheckStart(request, now)
        # Vary remote address to make sure the limit covers
        # the whole country, regardless of IP.
        request.remote_addr = '192.168.1.%d' % m
        now = now + 0.001

    # CheckStart for a country that isn't covered by a country-specific limit.
    request.headers['X-AppEngine-Country'] = 'UK'
    for m in range(11):
      self.ratelimiter.CheckStart(request, now)
      # Vary remote address to make sure the limit covers
      # the whole country, regardless of IP.
      request.remote_addr = '192.168.1.%d' % m
      now = now + 0.001

    # And regular rate limits work per-IP.
    request.remote_addr = '192.168.1.1'
    with self.assertRaises(ratelimiter.RateLimitExceeded):
      for m in range(ratelimiter.DEFAULT_LIMIT):  # pragma: no branch
        self.ratelimiter.CheckStart(request, now)
        # Vary remote address to make sure the limit covers
        # the whole country, regardless of IP.
        now = now + 0.001

  def testCheckEnd_SlowRequest(self):
    """We count one request for each 1000ms."""
    request, _ = testing_helpers.GetRequestObjects(
      project=self.project)
    request.headers[ratelimiter.COUNTRY_HEADER] = 'US'
    request.remote_addr = '192.168.1.1'
    start_time = 0.0

    # Send some requests, all under the limit.
    for _ in range(ratelimiter.DEFAULT_LIMIT-1):
      start_time = start_time + 0.001
      self.ratelimiter.CheckStart(request, start_time)
      now = start_time + 0.010
      self.ratelimiter.CheckEnd(request, now, start_time)

    # Now issue some more request, this time taking long
    # enough to get the cost threshold penalty.
    # Fast forward enough to impact a later bucket than the
    # previous requests.
    start_time = now + 120.0
    self.ratelimiter.CheckStart(request, start_time)

    # Take longer than the threshold to process the request.
    elapsed_ms = settings.ratelimiting_ms_per_count * 2
    now = start_time + elapsed_ms / 1000

    # The request finished, taking long enough to count as two.
    self.ratelimiter.CheckEnd(request, now, start_time)

    with self.assertRaises(ratelimiter.RateLimitExceeded):
      # One more request after the expensive query should
      # throw an excpetion.
      self.ratelimiter.CheckStart(request, start_time)

  def testCheckEnd_FastRequest(self):
    request, _ = testing_helpers.GetRequestObjects(
      project=self.project)
    request.headers[ratelimiter.COUNTRY_HEADER] = 'asdasd'
    request.remote_addr = '192.168.1.1'
    start_time = 0.0

    # Send some requests, all under the limit.
    for _ in range(ratelimiter.DEFAULT_LIMIT):
      self.ratelimiter.CheckStart(request, start_time)
      now = start_time + 0.01
      self.ratelimiter.CheckEnd(request, now, start_time)
      start_time = now + 0.01


class ApiRateLimiterTest(unittest.TestCase):

  def setUp(self):
    settings.ratelimiting_enabled = True
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.services = service_manager.Services(
      config=fake.ConfigService(),
      issue=fake.IssueService(),
      user=fake.UserService(),
      project=fake.ProjectService(),
    )

    self.client_id = '123456789'
    self.client_email = 'test@example.com'

    self.ratelimiter = ratelimiter.ApiRateLimiter()
    settings.api_ratelimiting_enabled = True

  def tearDown(self):
    self.testbed.deactivate()

  def testCheckStart_Allowed(self):
    now = 0.0
    self.ratelimiter.CheckStart(self.client_id, self.client_email, now)
    self.ratelimiter.CheckStart(self.client_id, None, now)
    self.ratelimiter.CheckStart(None, None, now)
    self.ratelimiter.CheckStart('anonymous', None, now)

  def testCheckStart_Rejected(self):
    now = 0.0
    keysets = ratelimiter._CreateApiCacheKeys(
        self.client_id, self.client_email, now)
    values = [{key: ratelimiter.DEFAULT_API_QPM + 1 for key in keyset} for
              keyset in keysets]
    for value in values:
      memcache.add_multi(value)
    with self.assertRaises(ratelimiter.ApiRateLimitExceeded):
      self.ratelimiter.CheckStart(self.client_id, self.client_email, now)

  def testCheckStart_Allowed_HigherQPMSpecified(self):
    """Client goes over the default, but has a higher QPM set."""
    now = 0.0
    keysets = ratelimiter._CreateApiCacheKeys(
        self.client_id, self.client_email, now)
    qpm_dict = client_config_svc.GetQPMDict()
    qpm_dict[self.client_email] = ratelimiter.DEFAULT_API_QPM + 10
    # The client used 1 request more than the default limit in each of the
    # 5 minutes in our 5 minute sample window, so 5 over to the total.
    values = [{key: ratelimiter.DEFAULT_API_QPM + 1 for key in keyset} for
              keyset in keysets]
    for value in values:
      memcache.add_multi(value)
    self.ratelimiter.CheckStart(self.client_id, self.client_email, now)
    del qpm_dict[self.client_email]

  def testCheckStart_Allowed_LowQPMIgnored(self):
    """Client specifies a QPM lower than the default and default is used."""
    now = 0.0
    keysets = ratelimiter._CreateApiCacheKeys(
        self.client_id, self.client_email, now)
    qpm_dict = client_config_svc.GetQPMDict()
    qpm_dict[self.client_email] = ratelimiter.DEFAULT_API_QPM - 10
    values = [{key: ratelimiter.DEFAULT_API_QPM for key in keyset} for
              keyset in keysets]
    for value in values:
      memcache.add_multi(value)
    self.ratelimiter.CheckStart(self.client_id, self.client_email, now)
    del qpm_dict[self.client_email]

  def testCheckStart_Rejected_LowQPMIgnored(self):
    """Client specifies a QPM lower than the default and default is used."""
    now = 0.0
    keysets = ratelimiter._CreateApiCacheKeys(
        self.client_id, self.client_email, now)
    qpm_dict = client_config_svc.GetQPMDict()
    qpm_dict[self.client_email] = ratelimiter.DEFAULT_API_QPM - 10
    values = [{key: ratelimiter.DEFAULT_API_QPM + 1 for key in keyset} for
              keyset in keysets]
    for value in values:
      memcache.add_multi(value)
    with self.assertRaises(ratelimiter.ApiRateLimitExceeded):
      self.ratelimiter.CheckStart(self.client_id, self.client_email, now)
    del qpm_dict[self.client_email]

  def testCheckEnd(self):
    start_time = 0.0
    keysets = ratelimiter._CreateApiCacheKeys(
        self.client_id, self.client_email, start_time)

    now = 0.1
    self.ratelimiter.CheckEnd(
        self.client_id, self.client_email, now, start_time)
    counters = memcache.get_multi(keysets[0])
    count = sum(counters.values())
    # No extra cost charged
    self.assertEqual(0, count)

    elapsed_ms = settings.ratelimiting_ms_per_count * 2
    now = start_time + elapsed_ms / 1000
    self.ratelimiter.CheckEnd(
        self.client_id, self.client_email, now, start_time)
    counters = memcache.get_multi(keysets[0])
    count = sum(counters.values())
    # Extra cost charged
    self.assertEqual(1, count)
