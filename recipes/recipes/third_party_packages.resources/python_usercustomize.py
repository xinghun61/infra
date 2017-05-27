# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file is installed as part of Chromium's Python packaging.

It will be installed into: //lib/python2.7/usercustomize.py

It customizes the installed Python environment to:
  - Incorporate system Python paths.

See:
https://chromium.googlesource.com/infra/infra/+/master/doc/packaging/python.md
"""

import os
import site
import sys

# Add system Python paths to the end of "sys.path".
def add_system_paths():
  def get_system_sitedirs():
    vers = sys.version[:3]
    if sys.platform == 'darwin':
      base = '/System/Library/Frameworks/Python.framework/Versions/' + vers
      yield os.path.join(base, 'Extras', 'lib', 'python')
    if sys.platform.startswith('linux'):
      for prefix in ('/usr/lib', '/usr/local/lib'):
        for pkg_dir in ('dist-packages', 'site-packages'):
          yield os.path.join(prefix, 'python' + vers, pkg_dir)

  for sitedir in get_system_sitedirs():
    if os.path.isdir(sitedir):
      site.addsitedir(sitedir)
add_system_paths()
