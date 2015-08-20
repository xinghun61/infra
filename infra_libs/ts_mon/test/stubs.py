# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from infra_libs.ts_mon import interface
from infra_libs.ts_mon import monitors
from infra_libs.ts_mon import targets


class MockState(interface.State):  # pragma: no cover

  def __init__(self):
    self.global_monitor = None
    self.default_target = None
    self.flush_mode = None
    self.flush_thread = None
    self.metrics = set()


def MockMonitor():  # pragma: no cover
  return mock.MagicMock(monitors.Monitor)


def MockTarget():  # pragma: no cover
  return mock.MagicMock(targets.Target)


class MockInterfaceModule(object):  # pragma: no cover

  def __init__(self):
    self._state = MockState()

  def add_argparse_options(self, parser):
    pass

  def process_argparse_options(self, opts):  # pylint: disable=unused-argument
    self._state.global_monitor = MockMonitor()
    self._state.default_target = MockTarget()

  def send(self, metric):
    pass

  def flush(self):
    pass

  def register(self, metric):
    pass

  def unregister(self, metric):
    pass
