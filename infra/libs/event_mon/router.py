# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import Queue
import logging
import threading
import time

from infra.libs.event_mon.log_request_lite_pb2 import LogRequestLite


def time_ms():
  """Return current timestamp in milliseconds."""
  return int(1000 * time.time())


class _Router(object):
  """Route events to the right destination.

  This object is meant to be a singleton, and is not part of the API.

  Usage:
  router = _Router()
  event = ChromeInfraEvent.LogEventLite(...)
  ... fill in event ...
  router.push_event(event)
  """
  def __init__(self, dry_run=True):
    # dry_run is meant for local testing and unit testing. When True, this
    # object should have no side effect.
    self.dry_run = dry_run

    self.event_queue = Queue.Queue()
    self._thread = threading.Thread(target=self._router)
    self._thread.daemon = True
    self._thread.start()

  def _router(self):
    while(True):  # pragma: no branch
      events = self.event_queue.get()
      if events is None:
        break

      # Set this time at the very last moment
      events.request_time_ms = time_ms()

      if not self.dry_run:  # pragma: no cover
        # TODO(pgervais): Actually do something
        pass

  def close(self, timeout=None):
    """
    Returns:
      success (bool): True if everything went well. Otherwise, there is no
        guarantee that all events have been properly sent to the remote.
    """
    timeout = timeout or 5
    self.event_queue.put(None)
    self._thread.join(timeout)
    # If the thread is still alive at this point, we can't but wait for a call
    # to sys.exit. Since we expect this function to be called at the end of the
    # program, it should come soon.
    return not self._thread.is_alive()

  def push_event(self, event):
    """Enqueue event to push to the collection service.

    This method offers no guarantee on return that the event have been pushed
    externally, as some buffering can take place.

    Args:
      event (LogRequestLite.LogEventLite): one single event.
    Returns:
      success (bool): False if an error happened. True means 'event accepted',
        but NOT 'event successfully pushed to the remote'.
    """
    if not isinstance(event, LogRequestLite.LogEventLite):
      logging.error('Invalid type for "event": %s (should be LogEventLite)'
                    % str(type(event)))
      return False

    # Dumb implementation, can be made more sophisticated (batching)
    request = LogRequestLite()
    request.log_event.extend((event,))  # copies the protobuf
    self.event_queue.put(request)
    return True
