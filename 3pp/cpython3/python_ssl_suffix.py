
# Copyright 2018 The Chromium Authors. All rights reserved.
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
  # pylint: disable=undefined-variable

  # Identify local system "cacert" paths.
  cabases = []
  if sys.platform == 'darwin':
    # On OS X, dump the system's cert list a max of once every 24 hours to
    # somewhere we can load into openssl.
    import time
    import subprocess

    prefix = sys.base_exec_prefix
    dumped_pem = os.path.join(prefix, 'cert.pem')

    # Dump if the file is missing or if it's older than 24 hours.
    do_dump = True
    try:
      do_dump = time.time() - os.stat(dumped_pem).st_mtime > 24*60*60
    except:  # pylint: disable=bare-except
      pass

    if do_dump:
      try:
        subprocess.call(
          ['security', 'find-certificate', '-a', '-p'],
          stdout=open(dumped_pem+'.tmp', 'wb'))
        os.rename(dumped_pem+'.tmp', dumped_pem)
      except:  # pylint: disable=bare-except
        pass
    cabases += [
        prefix,
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
      SSLContext.set_default_verify_paths = (
          lambda self: self.load_verify_locations(**kwargs))
      break

_attach_cacert_bundle()
