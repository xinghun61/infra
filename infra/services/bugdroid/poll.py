# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import threading
import time


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


class Poller(threading.Thread):

  def __init__(self, interval_in_minutes=15, setup_refresh_interval_minutes=0,
               run_once=False):
    threading.Thread.__init__(self, name=str(hash(self)))
    self.interval = interval_in_minutes * 60
    self.refresh_interval = setup_refresh_interval_minutes
    self.run_once = run_once

    if setup_refresh_interval_minutes:
      self.setup_refresh = (
          datetime.datetime.now() +
          datetime.timedelta(minutes=setup_refresh_interval_minutes))
    else:
      self.setup_refresh = None

  def execute(self):
    raise NotImplementedError()

  def setup(self):  # pylint: disable=R0201
    return True

  def run(self):
    try:
      while True:
        if self.setup_refresh and self.setup_refresh < datetime.datetime.now():
          LOGGER.info('Re-running Poller setup')
          self.setup()
          self.setup_refresh = (
              datetime.datetime.now() +
              datetime.timedelta(minutes=self.refresh_interval))

        self.execute()

        if self.run_once:
          return

        time.sleep(self.interval)
    except Exception:
      LOGGER.exception('Unhandled Poller exception.')

  def start(self):
    if self.setup():
      super(Poller, self).start()
