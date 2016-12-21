# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess


class DummyCloudtailFactory(object):
  def start(self, *_args, **_kwargs):
    raise OSError('Cloudtail is not configured')


class CloudtailFactory(object):
  """Object that knows how to start cloudtail processes."""

  def __init__(self, path, ts_mon_credentials):
    self._path = path
    self._ts_mon_credentials = ts_mon_credentials

  def start(self, log_name, stdin_fh, **popen_kwargs):
    """Starts cloudtail in a subprocess.  Thread-safe.

    Args:
      log_name: --log-id argument passed to cloudtail.
      stdin_fh: File object or descriptor to be connected to cloudtail's stdin.
      popen_kwargs: Any additional keyword arguments to pass to Popen.
    """

    args = [
        self._path, 'pipe',
        '--log-id', log_name,
        '--local-log-level', 'info',
    ]

    if self._ts_mon_credentials:
      args.extend(['--ts-mon-credentials', self._ts_mon_credentials])

    with open(os.devnull, 'w') as null_fh:
      subprocess.Popen(
          args,
          stdin=stdin_fh,
          stdout=null_fh,
          stderr=null_fh,
          **popen_kwargs)
