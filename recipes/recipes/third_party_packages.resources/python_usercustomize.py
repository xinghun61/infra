# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file is installed as part of Chromium's Python packaging.

It will be installed into: //lib/python2.7/usercustomize.py

It customizes the installed Python environment to:
  - Use the included "cacert.pem" certificate authority bundle, which will be
    included at: //lib/python2.7/cacert.pem

See:
https://chromium.googlesource.com/infra/infra/+/master/doc/packaging/python.md
"""

import os
import ssl
import sys

CACERT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cacert.pem")
def hack_set_default_verify_paths(self):
  self.load_verify_locations(cafile=CACERT)
ssl.SSLContext.set_default_verify_paths = hack_set_default_verify_paths
