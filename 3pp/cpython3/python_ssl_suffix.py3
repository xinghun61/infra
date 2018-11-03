
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
# The contents of this file are appended to "//lib/python3.7/ssl.py".

if sys.platform == 'darwin':
  def _load_certs_from_security_framework():
    import io
    import ctypes
    import ctypes.util
    from ctypes import byref, memmove, create_string_buffer, POINTER
    from ctypes import c_void_p, c_char, c_long, c_int32, c_uint32, c_char_p

    CF = ctypes.CDLL(ctypes.util.find_library('CoreFoundation'))
    CF.CFArrayAppendValue.argtypes = [c_void_p, c_void_p]
    CF.CFArrayCreateMutableCopy.argtypes = [c_void_p, c_long, c_void_p]
    CF.CFArrayCreateMutableCopy.restype = c_void_p
    CF.CFArrayGetValueAtIndex.argtypes = [c_void_p, c_int32]
    CF.CFArrayGetValueAtIndex.restype = c_void_p
    CF.CFDataGetBytePtr.argtypes = [c_void_p]
    CF.CFDataGetBytePtr.restype = c_void_p
    CF.CFDataGetLength.argtypes = [c_void_p]
    CF.CFDataGetLength.restype = c_long
    CF.CFDictionaryAddValue.argtypes = [c_void_p, c_void_p, c_void_p]
    CF.CFDictionaryAddValue.restype = None
    CF.CFDictionaryCreateMutable.restype = c_void_p
    CF.CFRelease.argtypes = [c_void_p]

    SEC = ctypes.CDLL(ctypes.util.find_library('Security'))
    SEC.SecItemCopyMatching.argtypes = [c_void_p, c_void_p]
    SEC.SecItemCopyMatching.restype = c_int32
    SEC.SecKeychainCopySearchList.argtypes = [c_void_p]
    SEC.SecKeychainCopySearchList.restype = c_int32
    SEC.SecKeychainOpen.argtypes = [c_char_p, c_void_p]
    SEC.SecKeychainOpen.restype = c_long

    errSecItemNotFound = -25300

    to_release = []
    try:
      lst = c_void_p(0)
      assert SEC.SecKeychainCopySearchList(byref(lst)) == 0
      to_release.append(lst)

      search_list = CF.CFArrayCreateMutableCopy(None, CF.CFArrayGetCount(lst)+1, lst)
      to_release.append(search_list)

      # attempt to add the SystemRootCertificates keychain to the search path
      # as well.
      root_cert_kc = c_void_p(0)
      root_certs = '/System/Library/Keychains/SystemRootCertificates.keychain'.encode('utf-8')
      if SEC.SecKeychainOpen(root_certs, byref(root_cert_kc)) == 0:
        CF.CFArrayAppendValue(search_list, root_cert_kc)
        to_release.append(root_cert_kc)

      def getRef(refname):
        return c_void_p.in_dll(SEC, refname)

      query = CF.CFDictionaryCreateMutable(None, 3, None, None)
      to_release.append(query)
      CF.CFDictionaryAddValue(
        query, getRef('kSecClass'), getRef('kSecClassCertificate'))
      CF.CFDictionaryAddValue(
        query, getRef('kSecMatchLimit'), getRef('kSecMatchLimitAll'))
      CF.CFDictionaryAddValue(
        query, getRef('kSecReturnData'), getRef('kCFBooleanTrue'))
      CF.CFDictionaryAddValue(
        query, getRef('kSecMatchSearchList'), search_list)

      items = c_void_p(0)
      result = SEC.SecItemCopyMatching(query, byref(items))
      if result == errSecItemNotFound:
        print("found zero certs in System Keychain", file=sys.stderr)
        return
      elif result != 0:
        print("failed to find certs in System Keychain: OSStatus(%r)" % result,
              file=sys.stderr)
        return
      to_release.append(items)

      cert_pem = io.StringIO()
      for i in range(CF.CFArrayGetCount(items)):
        data = CF.CFArrayGetValueAtIndex(items, i)
        siz = CF.CFDataGetLength(data)
        buf = bytearray(siz)
        char_array = c_char * len(buf)
        memmove(char_array.from_buffer(buf), CF.CFDataGetBytePtr(data), siz)
        cert_pem.write(DER_cert_to_PEM_cert(buf))

      return cert_pem.getvalue()
    finally:
      for itm in reversed(to_release):
        CF.CFRelease(itm)

  # On OS X, we can use the Security.framework to obtain all the certs
  # installed to the system keychains. We cache them as _system_cert_pem, then
  # make set_default_verify_paths() install them for each SSL context.
  #
  # If you install new certs in the various keychains, you'll need to restart
  # the python process... but that seems like a fair tradeoff to make.
  _system_cert_pem = _load_certs_from_security_framework()

  SSLContext.set_default_verify_paths = (
    lambda self: self.load_verify_locations(cadata=_system_cert_pem))

elif sys.platform == 'linux':
  def _attach_cacert_bundle():
    # pylint: disable=undefined-variable
    # Identify local system "cacert" paths.
    cabases = [
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
