#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cStringIO
import struct
import sys

import zipfile
from zipfile import _ECD_SIZE, _ECD_OFFSET, _ECD_LOCATION, _ECD_SIGNATURE
from zipfile import _CD_SIGNATURE, _CD_FILENAME_LENGTH, _CD_EXTRA_FIELD_LENGTH
from zipfile import _CD_COMMENT_LENGTH
from zipfile import stringEndArchive64, sizeEndCentDir64
from zipfile import sizeEndCentDir64Locator
from zipfile import stringCentralDir, structCentralDir
from zipfile import sizeCentralDir


# Heavily adapted from zipfile.py ZipFile._RealGetContents from
# the Python 2.7 distribution.
def _read_central_directory_offsets(zfile):
  """Read in the table of contents for the ZIP file."""

  fp = zfile.fp
  try:
    endrec = zipfile._EndRecData(fp)
  except IOError:
    raise zipfile.BadZipfile("File is not a zip file")
  if not endrec:
    raise zipfile.BadZipfile, "File is not a zip file"
  size_cd = endrec[_ECD_SIZE]             # bytes in central directory
  offset_cd = endrec[_ECD_OFFSET]         # offset of central directory

  # "concat" is zero, unless zip was concatenated to another file
  concat = endrec[_ECD_LOCATION] - size_cd - offset_cd
  if endrec[_ECD_SIGNATURE] == stringEndArchive64:
    # If Zip64 extension structures are present, account for them
    concat -= (sizeEndCentDir64 + sizeEndCentDir64Locator)

  # Go to start of central directory
  fp.seek(offset_cd + concat, 0)
  data = fp.read(size_cd)
  fp = cStringIO.StringIO(data)
  total = 0
  offsets = []
  while total < size_cd:
    # Tell gives use the offset inside the CD. We want the offset relative
    # to the beginning of file.
    offsets.append(fp.tell() + offset_cd + concat)
    centdir = fp.read(sizeCentralDir)
    if len(centdir) != sizeCentralDir:
      raise zipfile.BadZipfile("Truncated central directory")
    centdir = struct.unpack(structCentralDir, centdir)
    if centdir[_CD_SIGNATURE] != stringCentralDir:
      raise zipfile.BadZipfile("Bad magic number for central directory")

    # Skip everything else
    fp.seek(centdir[_CD_FILENAME_LENGTH]
            + centdir[_CD_EXTRA_FIELD_LENGTH]
            + centdir[_CD_COMMENT_LENGTH], 1)

    # update total bytes read from central directory
    total = (total + sizeCentralDir + centdir[_CD_FILENAME_LENGTH]
             + centdir[_CD_EXTRA_FIELD_LENGTH]
             + centdir[_CD_COMMENT_LENGTH])

  return offsets


def reset_all_timestamps_in_zip(filename):
  """Reset all file timestamps to 1980-00-00 00:00 in a zip file.
  """
  with open(filename, 'r+b') as f:
    # Collect file headers and central directory offsets.
    zipf = zipfile.ZipFile(f)
    offsets = [zipinfo.header_offset for zipinfo in zipf.infolist()]
    cd_offsets = _read_central_directory_offsets(zipf)

    for offset in offsets:
      # Timestamp is four bytes starting 10 bytes after start of header.
      # https://en.wikipedia.org/wiki/Zip_(file_format)
      f.seek(offset + 10)
      f.write('\0\0\0\0')

    for offset in cd_offsets:
      # Timestamp is four bytes starting 12 bytes after start of each file
      # header in the central directory.
      # https://en.wikipedia.org/wiki/Zip_(file_format)
      f.seek(offset + 12)
      f.write('\0\0\0\0')


if __name__ == '__main__':
  reset_all_timestamps_in_zip(sys.argv[1])
