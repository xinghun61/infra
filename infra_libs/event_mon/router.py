# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import random
import time

import httplib2

from infra_libs.event_mon.log_request_lite_pb2 import LogRequestLite
from infra_libs.event_mon.chrome_infra_log_pb2 import ChromeInfraEvent
import infra_libs

def time_ms():
  """Return current timestamp in milliseconds."""
  return int(1000 * time.time())


def backoff_time(attempt, retry_backoff=2., max_delay=30.):
  """Compute randomized exponential backoff time.

  Args:
    attempt (int): attempt number, starting at zero.

  Keyword Args:
    retry_backoff(float): backoff time on the first attempt.
    max_delay(float): maximum returned value.
  """
  delay = retry_backoff * (2 ** attempt)
  # Add +-25% of variation.
  delay += delay * ((random.random() - 0.5) / 2.)
  return min(delay, max_delay)


class _Router(object):
  """Route events to the right destination.

  This object is meant to be a singleton, and is not part of the API.

  Usage:
  router = _Router()
  event = ChromeInfraEvent.LogEventLite(...)
  ... fill in event ...
  router.push_event(event)
  """
  def __init__(self, cache, endpoint=None, timeout=10):
    # cache is defined in config.py. Passed as a parameter to avoid
    # a circular import.

    # endpoint == None means 'dry run'. No data is sent.
    self.endpoint = endpoint
    self.http = httplib2.Http(timeout=timeout)
    self.cache = cache

    if self.endpoint and self.cache['service_account_creds']:
      logging.debug('Activating OAuth2 authentication.')
      self.http = infra_libs.get_authenticated_http(
        self.cache['service_account_creds'],
        service_accounts_creds_root=self.cache['service_accounts_creds_root'],
        scope='https://www.googleapis.com/auth/cclog'
      )

  def _post_to_endpoint(self, events, try_num=3, retry_backoff=2.):
    """Post protobuf to endpoint.

    Args:
      events(LogRequestLite): the protobuf to post.

    Keyword Args:
      try_num(int): max number of http requests send to the endpoint.
      retry_backoff(float): time in seconds before retrying posting to the
         endpoint. Randomized exponential backoff is applied on subsequent
         retries.

    Returns:
      success(bool): whether pushing to the endpoint succeeded or not.
    """
    # Set this time at the very last moment
    events.request_time_ms = time_ms()
    if self.endpoint:  # pragma: no cover
      logging.info('event_mon: POSTing events to %s', self.endpoint)

      for attempt in xrange(try_num - 1):
        response, _ = self.http.request(
          uri=self.endpoint,
          method='POST',
          headers={'Content-Type': 'application/octet-stream'},
          body=events.SerializeToString()
        )

        if response.status == 200:
          return True

        logging.error('failed to POST data to %s (attempt %d)',
                      self.endpoint, attempt)
        logging.error('data: %s', str(events)[:200])

        time.sleep(backoff_time(attempt, retry_backoff=retry_backoff))
      return False

    else:
      infra_events = [str(ChromeInfraEvent.FromString(
        ev.source_extension)) for ev in events.log_event]
      logging.info('Fake post request. Sending:\n%s',
                   '\n'.join(infra_events))
      return True

  def close(self, timeout=None): # pylint: disable=unused-argument
    """
    Returns:
      success (bool): True if everything went well. Otherwise, there is no
        guarantee that all events have been properly sent to the remote.
    """
    # This is a stub now, for backward compatibility. Maybe we'll use that
    # again if a thread is re-added to the lib.
    logging.debug('event_mon: closing.')
    return True

  def push_event(self, log_events):
    """Enqueue event to push to the collection service.

    This method offers no guarantee on return that the event have been pushed
    externally, as some buffering can take place.

    Args:
      log_events (LogRequestLite.LogEventLite or list/tuple of): events.
    Returns:
      success (bool): False if an error happened. True means 'event accepted',
        but NOT 'event successfully pushed to the remote'.
    """
    if isinstance(log_events, LogRequestLite.LogEventLite):
      log_events = (log_events,)

    if not isinstance(log_events, (list, tuple)):
      logging.error('Invalid type for "event", should be LogEventLite or '
                    'list of. Got %s' % str(type(log_events)))
      return False

    request_p = LogRequestLite()
    request_p.log_source_name = 'CHROME_INFRA'
    request_p.log_event.extend(log_events)  # copies the protobuf
    return self._post_to_endpoint(request_p)
