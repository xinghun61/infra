
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
    def load_certs_from_security_framework(ssl_context):
      import io
      import ctypes
      import ctypes.util
      from ctypes import byref, memmove, c_void_p, c_char, c_long, c_int32

      SEC = ctypes.CDLL(ctypes.util.find_library('Security'))
      CF = ctypes.CDLL(ctypes.util.find_library('CoreFoundation'))

      CF.CFDictionaryCreateMutable.restype = c_void_p
      CF.CFDictionaryAddValue.restype = None
      CF.CFDictionaryAddValue.argtypes = [c_void_p, c_void_p, c_void_p]
      SEC.SecItemCopyMatching.restype = c_int32
      SEC.SecItemCopyMatching.argtypes = [c_void_p, c_void_p]
      CF.CFArrayGetValueAtIndex.restype = c_void_p
      CF.CFArrayGetValueAtIndex.argtypes = [c_void_p, c_int32]
      CF.CFRelease.argtypes = [c_void_p]
      CF.CFDataGetLength.restype = c_long
      CF.CFDataGetLength.argtypes = [c_void_p]
      CF.CFDataGetBytePtr.restype = c_void_p
      CF.CFDataGetBytePtr.argtypes = [c_void_p]
      errSecItemNotFound = -25300

      def getConst(refname):
        return c_void_p.in_dll(SEC, refname)

      query = CF.CFDictionaryCreateMutable(None, 3, None, None)
      # We want to find all the "Certificate" items, in any keychain that our
      # process has access to.
      CF.CFDictionaryAddValue(
        query, getConst('kSecClass'), getConst('kSecClassCertificate'))
      # We want ALL the certs loaded into the system (the default would only
      # return the first cert).
      CF.CFDictionaryAddValue(
        query, getConst('kSecMatchLimit'), getConst('kSecMatchLimitAll'))
      # Return raw data (CFDataRef's). Since kSecClass == kSecClassCertificate,
      # these will be DER-encoded certs. Not specifying this will return
      # SecCertificateRef's instead, which requires an extra function call
      # to get them as DER-encoded data.
      CF.CFDictionaryAddValue(
        query, getConst('kSecReturnData'), getConst('kCFBooleanTrue'))

      # Items is going to be a CFArrayRef, once SecItemCopyMatching fills it in.
      items = c_void_p(0)
      result = SEC.SecItemCopyMatching(query, byref(items))
      CF.CFRelease(query)  # done with the query dict
      if result == errSecItemNotFound:
        print('found zero certs in System Keychain', file=sys.stderr)
        return
      elif result != 0:
        print('failed to find certs in System Keychain: OSStatus(%r)' % result,
              file=sys.stderr)
        return

      cert_pem = io.StringIO()
      for i in range(CF.CFArrayGetCount(items)):
        data = CF.CFArrayGetValueAtIndex(items, i)
        siz = CF.CFDataGetLength(data)
        buf = bytearray(siz)
        char_array = c_char * len(buf)
        memmove(char_array.from_buffer(buf), CF.CFDataGetBytePtr(data), siz)
        cert_pem.write(DER_cert_to_PEM_cert(buf))
      CF.CFRelease(items)

      ssl_context.load_verify_locations(cadata=cert_pem.getvalue())
      return

    # On OS X, we can use the Security.framework to obtain all the certs
    # installed to the system keychain.
    SSLContext.set_default_verify_paths = load_certs_from_security_framework
    return

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
