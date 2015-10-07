# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ctypes
import functools
import logging
import os
import signal
import subprocess
import sys

from infra.libs.buildbot import master
from infra.services.mastermon import pollers
from infra_libs import ts_mon


RESULTS_FILE = '/var/log/chrome-infra/status_logger-%s/ts_mon.log'


def set_deathsig(sig):  # pragma: no cover
  """Wrapper around the prctl(PR_SET_PDEATHSIG) system call.

  From the manual page:

      Set the parent process death signal of the calling process to sig
      (either a signal value in the range 1..maxsig, or 0 to clear).  This is
      the signal that the calling process will get when its parent dies.  This
      value is cleared for the child of a fork(2) and (since Linux 2.4.36 /
      2.6.23) when executing a set-user-ID or set-group-ID binary.
  """

  assert sys.platform == 'linux2', 'set_deathsig only works on Linux'

  PR_SET_PDEATHSIG = 1

  libc = ctypes.cdll.LoadLibrary('libc.so.6')
  ret = libc.prctl(PR_SET_PDEATHSIG, sig, 0, 0, 0)
  if ret != 0:  # pragma: no cover
    raise OSError('prctl failed', ctypes.get_errno())


class MasterMonitor(object):
  up = ts_mon.BooleanMetric('buildbot/master/up')

  POLLER_CLASSES = [
    pollers.VarzPoller,
  ]

  def __init__(self, url, name=None, results_file=None, log_file=None,
               cloudtail_path=None):
    if name is None:
      logging.info('Creating monitor for %s', url)
      self._metric_fields = {}
      self._name = url
    else:
      logging.info('Creating monitor for %s on %s', name, url)
      self._metric_fields = {'master': name}
      self._name = name

    self._pollers = [
        cls(url, self._metric_fields) for cls in self.POLLER_CLASSES]

    if results_file is not None:
      # Ignore events that were posted while we weren't listening.
      # That will avoid posting a lot of build events at the wrong time.
      if os.path.isfile(results_file):
        pollers.safe_remove(results_file)
      self._pollers.append(pollers.FilePoller(
        results_file, self._metric_fields))

    self._cloudtail = None
    if log_file is not None and cloudtail_path is not None and name is not None:
      logging.info('Starting cloudtail for %s on %s', name, log_file)
      cloudtail_args = [
          cloudtail_path,
          'tail',
          '--path', log_file,
          '--resource-id', name,
          '--log-id', 'master_twistd.log',
          '--local-log-level', 'info',
      ]

      try:
        # set_deathsig ensures the cloudtail will flush and exit when mastermon
        # exits.
        self._cloudtail = subprocess.Popen(cloudtail_args,
            preexec_fn=functools.partial(set_deathsig, signal.SIGINT))
      except OSError:
        logging.exception('Failed to start cloudtail with args %s',
                          cloudtail_args)

  def poll(self):
    logging.info('Polling %s', self._name)

    for poller in self._pollers:
      if not poller.poll():
        self.up.set(False, fields=self._metric_fields)
        break
    else:
      self.up.set(True, fields=self._metric_fields)


def create_from_mastermap(build_dir, hostname,
                          cloudtail_path):  # pragma: no cover
  logging.info('Creating monitors from mastermap for host %s', hostname)
  return _create_from_mastermap(
      build_dir,
      master.get_mastermap_for_host(build_dir, hostname),
      cloudtail_path)


def _path_to_twistd_log(build_dir, dirname):
  paths = [
      os.path.join(build_dir, 'masters', dirname, 'twistd.log'),
      os.path.join(os.path.dirname(build_dir), 'build_internal', 'masters',
                   dirname, 'twistd.log'),
  ]
  for path in paths:
    if os.path.exists(path):
      return path
  return None


def _create_from_mastermap(build_dir, mastermap, cloudtail_path):
  return [
      MasterMonitor('http://localhost:%d' % entry['port'],
                    name=entry['dirname'],
                    results_file=RESULTS_FILE % entry['dirname'],
                    log_file=_path_to_twistd_log(build_dir, entry['dirname']),
                    cloudtail_path=cloudtail_path)
      for entry
      in mastermap]
