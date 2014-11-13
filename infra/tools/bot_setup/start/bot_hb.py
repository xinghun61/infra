# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs a heartbeat daemon in a separate thread."""

import copy
import os
import time
import threading

# pylint: disable=F0401


SECRET_FILE = '.heartbeat.key'
URLS = ['https://chrome-heartbeats.appspot.com/heartbeat']


class HeartbeatRunner(object):
  def __init__(self, slave_name, root_dir, heartbeat_cls=None):
    if not heartbeat_cls:  # pragma: no cover
      # TODO(hinoka): Hearbeat doesn't have coverage right now crbug.com/432638
      from infra.tools.heartbeat import heartbeat
      heartbeat_cls = heartbeat
    self.heartbeat = heartbeat_cls
    self.name = slave_name
    self.secret_file = os.path.join(root_dir, SECRET_FILE)
    self.secret = self.heartbeat.get_secret(self.secret_file)
    self.thread = None
    self.extra_data = {}
    self.extra_data_lock = threading.Lock()

  def set(self, key, value):
    with self.extra_data_lock:
      self.extra_data[key] = value

  def get_extra_data(self):
    with self.extra_data_lock:
      return copy.copy(self.extra_data)

  def _send_heartbeat(self):
    data = {
        'name': self.name,
        'status': 0,
        'message': 'OK',
        'time': time.time(),
        'id': self.heartbeat.get_id(),
    }
    data.update(self.get_extra_data())
    signed_message = self.heartbeat.get_hashed_message(data, self.secret)
    result = self.heartbeat.send(signed_message, URLS)
    if result == 402:
      signed_message['key'] = self.secret
      self.heartbeat.send(signed_message, URLS)

  def _runner(self):  # pragma: no cover
    while True:
      try:
        self._send_heartbeat()
      except Exception as e:
        print 'Hearbeat exception %s' % e
      time.sleep(60)


  def run(self):  # pragma: no cover
    self.thread = threading.Thread(target=self._runner)
    self.thread.daemon = True
    self.thread.start()

