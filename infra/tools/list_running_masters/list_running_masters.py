# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for List_running_masters."""

import logging
import os
import psutil


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)


def _is_buildbot_cmdline(cmdline):
  """Returns (bool): True if a process is a BuildBot process.

  We determine this by testing if it has the command pattern:
  [...] [.../]python [.../]twistd [...]

  Args:
    cmdline (list): The command line list.
  """
  return any((os.path.basename(cmdline[i]) == 'python' and
              os.path.basename(cmdline[i+1]) == 'twistd')
             for i in xrange(len(cmdline)-1))


def get_running_masters():
  """Probes the currently-running masters.

  Returns (dict): A dictionary mapping running master names to a list of their
      PIDs.
  """
  bb_dirs = {}
  for proc in psutil.process_iter():
    try:
      cmdline = proc.cmdline()
      cwd = proc.getcwd()
    except (psutil.AccessDenied, OSError, IOError):
      continue
    if not _is_buildbot_cmdline(cmdline):
      continue

    master_name = os.path.basename(cwd)
    bb_dirs.setdefault(master_name, set()).add(proc.pid)
  for k, v in bb_dirs.iteritems():
    bb_dirs[k] = sorted(v)
  return bb_dirs
