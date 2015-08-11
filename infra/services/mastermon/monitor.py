# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from infra.libs.buildbot import master
from infra.services.mastermon import pollers
from infra_libs import ts_mon


class MasterMonitor(object):
  up = ts_mon.BooleanMetric('buildbot/master/up')

  POLLER_CLASSES = [
    pollers.VarzPoller,
  ]

  def __init__(self, url, name=None):
    if name is None:
      logging.info('Created monitor for %s', url)
      self._metric_fields = {}
      self._name = url
    else:
      logging.info('Created monitor for %s on %s', name, url)
      self._metric_fields = {'master': name}
      self._name = name

    self._pollers = [
        cls(url, self._metric_fields) for cls in self.POLLER_CLASSES]

  def poll(self):
    logging.info('Polling %s', self._name)

    for poller in self._pollers:
      if not poller.poll():
        self.up.set(False, fields=self._metric_fields)
        break
    else:
      self.up.set(True, fields=self._metric_fields)


def create_from_mastermap(build_dir, hostname):  # pragma: no cover
  logging.info('Creating monitors from mastermap for host %s', hostname)
  return _create_from_mastermap(
      master.get_mastermap_for_host(build_dir, hostname))


def _create_from_mastermap(mastermap):
  return [
      MasterMonitor('http://localhost:%d' % entry['port'], entry['dirname'])
      for entry
      in mastermap]
