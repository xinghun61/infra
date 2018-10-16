# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Request rate limiting implementation.

This is intented to be used for automatic DDoS protection.

"""

import datetime
import logging
import os
import settings
import time

from infra_libs import ts_mon

from google.appengine.api import memcache
from google.appengine.api.modules import modules
from google.appengine.api import users

from services import client_config_svc


N_MINUTES = 5
EXPIRE_AFTER_SECS = 60 * 60
DEFAULT_LIMIT = 60 * N_MINUTES  # 300 requests in 5 minutes is 1 QPS.
DEFAULT_API_QPM = 200

ANON_USER = 'anon'

COUNTRY_HEADER = 'X-AppEngine-Country'

COUNTRY_LIMITS = {
  # Two-letter country code: max requests per N_MINUTES
  # This limit will apply to all requests coming
  # from this country.
  # To add a country code, see GAE logs and use the
  # appropriate code from https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2
  # E.g., 'cn': 300,  # Limit to 1 QPS.
}

# Modules not in this list will not have rate limiting applied by this
# class.
MODULE_WHITELIST = ['default']

def _CacheKeys(request, now_sec):
  """ Returns an array of arrays. Each array contains strings with
      the same prefix and a timestamp suffix, starting with the most
      recent and decrementing by 1 minute each time.
  """
  now = datetime.datetime.fromtimestamp(now_sec)
  country = request.headers.get(COUNTRY_HEADER, 'ZZ')
  ip = request.remote_addr
  minute_buckets = [now - datetime.timedelta(minutes=m) for m in
                    range(N_MINUTES)]
  user = users.get_current_user()
  user_email = user.email() if user else ANON_USER

  # <IP, country, user_email> to be rendered into each key prefix.
  prefixes = []

  # All logged-in users get a per-user rate limit, regardless of IP and country.
  if user:
    prefixes.append(['ALL', 'ALL', user.email()])
  else:
    # All anon requests get a per-IP ratelimit.
    prefixes.append([ip, 'ALL', 'ALL'])

  # All requests from a problematic country get a per-country rate limit,
  # regardless of the user (even a non-logged-in one) or IP.
  if country in COUNTRY_LIMITS:
    prefixes.append(['ALL', country, 'ALL'])

  keysets = []
  for prefix in prefixes:
    keysets.append(['ratelimit-%s-%s' % ('-'.join(prefix),
        str(minute_bucket.replace(second=0, microsecond=0)))
        for minute_bucket in minute_buckets])

  return keysets, country, ip, user_email


def _CreateApiCacheKeys(client_id, client_email, now_sec):
  country = os.environ.get('HTTP_X_APPENGINE_COUNTRY')
  ip = os.environ.get('REMOTE_ADDR')
  now = datetime.datetime.fromtimestamp(now_sec)
  minute_buckets = [now - datetime.timedelta(minutes=m) for m in
                    range(N_MINUTES)]
  minute_strs = [str(minute_bucket.replace(second=0, microsecond=0))
                 for minute_bucket in minute_buckets]
  keys = []

  if client_id and client_id != 'anonymous':
    keys.append(['apiratelimit-%s-%s' % (client_id, minute_str)
                 for minute_str in minute_strs])
  if client_email:
    keys.append(['apiratelimit-%s-%s' % (client_email, minute_str)
                 for minute_str in minute_strs])
  else:
    keys.append(['apiratelimit-%s-%s' % (ip, minute_str)
                 for minute_str in minute_strs])
    if country in COUNTRY_LIMITS:
      keys.append(['apiratelimit-%s-%s' % (country, minute_str)
                   for minute_str in minute_strs])

  return keys


class RateLimiter(object):

  blocked_requests = ts_mon.CounterMetric(
      'monorail/ratelimiter/blocked_request',
      'Count of requests that exceeded the rate limit and were blocked.',
      None)
  limit_exceeded = ts_mon.CounterMetric(
      'monorail/ratelimiter/rate_exceeded',
      'Count of requests that exceeded the rate limit.',
      None)
  cost_thresh_exceeded = ts_mon.CounterMetric(
      'monorail/ratelimiter/cost_thresh_exceeded',
      'Count of requests that were expensive to process',
      None)
  checks = ts_mon.CounterMetric(
      'monorail/ratelimiter/check',
      'Count of checks done, by fail/success type.',
      [ts_mon.StringField('type')])

  def __init__(self, _cache=memcache, fail_open=True, **_kwargs):
    self.fail_open = fail_open

  def CheckStart(self, request, now=None):
    if (modules.get_current_module_name() not in MODULE_WHITELIST or
          users.is_current_user_admin()):
      return
    logging.info('X-AppEngine-Country: %s' %
      request.headers.get(COUNTRY_HEADER, 'ZZ'))

    if now is None:
      now = time.time()

    keysets, country, ip, user_email  = _CacheKeys(request, now)
    # There are either two or three sets of keys in keysets.
    # Three if the user's country is in COUNTRY_LIMITS, otherwise two.
    self._AuxCheckStart(
        keysets, COUNTRY_LIMITS.get(country, DEFAULT_LIMIT),
        settings.ratelimiting_enabled,
        RateLimitExceeded(country=country, ip=ip, user_email=user_email))

  def _AuxCheckStart(self, keysets, limit, ratelimiting_enabled,
                     exception_obj):
    for keys in keysets:
      count = 0
      try:
        counters = memcache.get_multi(keys)
        count = sum(counters.values())
        self.checks.increment({'type': 'success'})
      except Exception as e:
        logging.error(e)
        if not self.fail_open:
          self.checks.increment({'type': 'fail_closed'})
          raise exception_obj
        self.checks.increment({'type': 'fail_open'})

      if count > limit:
        # Since webapp2 won't let us return a 429 error code
        # <http://tools.ietf.org/html/rfc6585#section-4>, we can't
        # monitor rate limit exceeded events with our standard tools.
        # We return a 400 with a custom error message to the client,
        # and this logging is so we can monitor it internally.
        logging.info('%s, %d' % (exception_obj.message, count))

        self.limit_exceeded.increment()

        if ratelimiting_enabled:
          self.blocked_requests.increment()
          raise exception_obj

      k = keys[0]
      # Only update the latest *time* bucket for each prefix (reverse chron).
      memcache.add(k, 0, time=EXPIRE_AFTER_SECS)
      memcache.incr(k, initial_value=0)

  def CheckEnd(self, request, now, start_time):
    """If a request was expensive to process, charge some extra points
    against this set of buckets.
    We pass in both now and start_time so we can update the buckets
    based on keys created from start_time instead of now.
    now and start_time are float seconds.
    """
    if (modules.get_current_module_name() not in MODULE_WHITELIST or
        not settings.ratelimiting_cost_enabled):
      return

    elapsed_ms = (now - start_time) * 1000
    # Would it kill the python lib maintainers to have timedelta.total_ms()?
    if elapsed_ms < settings.ratelimiting_cost_thresh_ms:
      return

    # TODO: Look into caching the keys instead of generating them twice
    # for every request. Say, return them from CheckStart so they can
    # be bassed back in here later.
    keysets, country, ip, user_email  = _CacheKeys(request, start_time)

    self._AuxCheckEnd(
        keysets,
        'Rate Limit Cost Threshold Exceeded: %s, %s, %s' % (
            country, ip, user_email),
        settings.ratelimiting_cost_penalty)

  def _AuxCheckEnd(self, keysets, log_str, ratelimiting_cost_penalty):
    self.cost_thresh_exceeded.increment()
    for keys in keysets:
      logging.info(log_str)

      # Only update the latest *time* bucket for each prefix (reverse chron).
      k = keys[0]
      memcache.add(k, 0, time=EXPIRE_AFTER_SECS)
      memcache.incr(k, delta=ratelimiting_cost_penalty, initial_value=0)


class ApiRateLimiter(RateLimiter):

  blocked_requests = ts_mon.CounterMetric(
      'monorail/apiratelimiter/blocked_request',
      'Count of requests that exceeded the rate limit and were blocked.',
      None)
  limit_exceeded = ts_mon.CounterMetric(
      'monorail/apiratelimiter/rate_exceeded',
      'Count of requests that exceeded the rate limit.',
      None)
  cost_thresh_exceeded = ts_mon.CounterMetric(
      'monorail/apiratelimiter/cost_thresh_exceeded',
      'Count of requests that were expensive to process',
      None)
  checks = ts_mon.CounterMetric(
      'monorail/apiratelimiter/check',
      'Count of checks done, by fail/success type.',
      [ts_mon.StringField('type')])

  #pylint: disable=arguments-differ
  def CheckStart(self, client_id, client_email, now=None):
    if now is None:
      now = time.time()

    keysets = _CreateApiCacheKeys(client_id, client_email, now)
    qpm_limit = client_config_svc.GetQPMDict().get(
        client_email, DEFAULT_API_QPM)
    window_limit = qpm_limit * N_MINUTES
    self._AuxCheckStart(
        keysets, window_limit,
        settings.api_ratelimiting_enabled,
        ApiRateLimitExceeded(client_id, client_email))

  #pylint: disable=arguments-differ
  def CheckEnd(self, client_id, client_email, now, start_time):
    if not settings.ratelimiting_cost_enabled:
      return

    elapsed_ms = (now - start_time) * 1000

    if elapsed_ms < settings.api_ratelimiting_cost_thresh_ms:
      return

    keysets = _CreateApiCacheKeys(client_id, client_email, start_time)
    self._AuxCheckEnd(
        keysets,
        'API Rate Limit Cost Threshold Exceeded: %s, %s' % (
            client_id, client_email),
        settings.api_ratelimiting_cost_penalty)


class RateLimitExceeded(Exception):
  def __init__(self, country=None, ip=None, user_email=None, **_kwargs):
    self.country = country
    self.ip = ip
    self.user_email = user_email
    message = 'RateLimitExceeded: %s, %s, %s' % (
        self.country, self.ip, self.user_email)
    super(RateLimitExceeded, self).__init__(message)


class ApiRateLimitExceeded(Exception):
  def __init__(self, client_id, client_email):
    self.client_id = client_id
    self.client_email = client_email
    message = 'RateLimitExceeded: %s, %s' % (
        self.client_id, self.client_email)
    super(ApiRateLimitExceeded, self).__init__(message)
