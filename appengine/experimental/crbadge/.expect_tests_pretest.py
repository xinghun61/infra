# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=undefined-variable

# Crazy hack, because of appengine.
import os
import sys


def _fix_sys_path_for_appengine(pretest_filename):
  infra_base_dir = os.path.abspath(pretest_filename)
  pos = infra_base_dir.rfind('/infra/appengine')
  if pos == -1:
    return
  infra_base_dir = infra_base_dir[:pos + len('/infra')]

  # Remove the base infra directory from the path, since this isn't available
  # on appengine.
  sys.path.remove(infra_base_dir)

  # Add the google_appengine directory.
  sys.path.insert(0,
      os.path.join(os.path.dirname(infra_base_dir), 'google_appengine'))

  import dev_appserver as pretest_dev_appserver
  pretest_dev_appserver.fix_sys_path()


def _load_appengine_config(pretest_filename):
  app_dir = os.path.abspath(os.path.dirname(pretest_filename))
  if not os.path.exists(os.path.join(app_dir, 'appengine_config.py')):
    return

  inserted = False
  if app_dir not in sys.path:
    sys.path.insert(0, app_dir)
    inserted = True
  import appengine_config  # Unused Variable pylint: disable=W0612
  if inserted:
    sys.path.remove(app_dir)


# Using pretest_filename is magic, because it is available in the locals() of
# the script which execfiles this file.
_fix_sys_path_for_appengine(pretest_filename)

# Load appengine_config from the appengine project to ensure that any changes to
# configuration there are available to the tests (e.g. sys.path modifications,
# namespaces, etc.). This is according to
# https://cloud.google.com/appengine/docs/python/tools/localunittesting
_load_appengine_config(pretest_filename)
