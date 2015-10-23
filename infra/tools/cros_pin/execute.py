# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess

from infra.tools.cros_pin.logger import LOGGER


def call(cmd, cwd=None, dry_run=False):
  LOGGER.info("Executing command %s (cwd=%s)", cmd, (cwd or os.getcwd()))
  if dry_run:
    LOGGER.info('Dry Run: Not actually executing.')
    return (0, "")

  output = []
  proc = subprocess.Popen(
      cmd,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      cwd=cwd)

  for line in iter(proc.stdout.readline, b''):
    LOGGER.debug('[%s]: %s', cmd[0], line.rstrip())
    output.append(line)
  proc.wait()

  return proc.returncode, ''.join(output)


def check_call(cmd, **kwargs):
  rv, stdout = call(cmd, **kwargs)
  if rv != 0:
    raise subprocess.CalledProcessError(rv, cmd, None)
  return stdout
