# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains util functions that local scripts can use."""

import logging
import os
import subprocess
import sys


def SetUpSystemPaths():  # pragma: no cover
  """Sets system paths so as to import modules in findit, third_party and
  appengine."""
  findit_root_dir = os.path.join(os.path.dirname(__file__), os.path.pardir)
  third_party_dir = os.path.join(findit_root_dir, 'third_party')
  appengine_sdk_dir = os.path.join(findit_root_dir, os.path.pardir,
                                   os.path.pardir, os.path.pardir,
                                   'google_appengine')

  # Add App Engine SDK dir to sys.path.
  sys.path.insert(1, appengine_sdk_dir)
  sys.path.insert(1, third_party_dir)
  import dev_appserver
  dev_appserver.fix_sys_path()

  # Add Findit root dir to sys.path so that modules in Findit is available.
  sys.path.insert(1, findit_root_dir)


# TODO(katesonia): Add local cache for this function.
def GetCommandOutput(command):
  """Gets the output stream of executable command.

  Args:
    command (str): Command to execute to get output.

  Return:
    Output steam of the command.
  """
  p = subprocess.Popen(
      command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
  stdoutdata, stderrdata = p.communicate()

  if p.returncode != 0:
    logging.error('Error running command %s: %s', command, stderrdata)
    return None

  return stdoutdata
