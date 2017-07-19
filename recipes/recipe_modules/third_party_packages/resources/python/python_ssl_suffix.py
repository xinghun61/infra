# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This file is appended to Chromium Python's "ssl.py" module.
#
# Chromium modifies "ssl.py" to set this default SSL certificate path to the
# sort of path a native system Python would include. We determine this by
# probing the local environment on startup and seeing if we can identfy an
# OpenSSL certificate layout.
#
# If we can't, no default certificate authority bundle will be installed.
#
# The contents of this file are appended to "//lib/python2.7/ssl.py" during
# bundle creation. See:
# https://chromium.googlesource.com/infra/infra/+/master/doc/packaging/python.md

def _attach_cacert_bundle():
  import os
  import ssl
  import sys

  # Identify local system "cacert" paths.
  cabases = []
  if sys.platform == 'darwin':
    cabases += [
        '/System/Library/OpenSSL',
    ]
  if sys.platform.startswith('linux'):
    cabases += [
        '/etc/ssl',
        '/usr/lib/ssl',
    ]

  # Determine which certificate configuration to use by probing the system and
  # looking in known system SSL certificate locations.
  kwargs = {}
  for cabase in cabases:
    cafile = os.path.join(cabase, 'cert.pem')
    if os.path.isfile(cafile):
      kwargs['cafile'] = cafile

    capath = os.path.join(cabase, 'certs')
    if os.path.isdir(capath):
      kwargs['capath'] = capath

    if kwargs:
      ssl.SSLContext.set_default_verify_paths = (
          lambda(self): self.load_verify_locations(**kwargs))
      break

_attach_cacert_bundle()
