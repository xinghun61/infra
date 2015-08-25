# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ctypes
from ctypes import wintypes, windll

# https://msdn.microsoft.com/en-us/library/windows/desktop/bb762494(v=vs.85).aspx
CSIDL_COMMON_APPDATA = 35

_SHGetFolderPath = windll.shell32.SHGetFolderPathW
_SHGetFolderPath.argtypes = [wintypes.HWND,
                             ctypes.c_int,
                             wintypes.HANDLE,
                             wintypes.DWORD,
                             wintypes.LPCWSTR]


class WindowsError(Exception):
  """Error code returned from a Windows API call.

  Values are documented here:
  https://msdn.microsoft.com/en-us/library/windows/desktop/aa378137(v=vs.85).aspx
  """
  pass


def common_appdata_path():
  """Returns the path to the common appdata directory.

  This is usually one of:
    C:\Documents and Settings\All Users\Application Data
    C:\ProgramData
  """

  buf = wintypes.create_unicode_buffer(wintypes.MAX_PATH)
  ret = _SHGetFolderPath(0, CSIDL_COMMON_APPDATA, 0, 0, buf)
  if ret != 0:
    raise WindowsError(ret)

  return buf.value
