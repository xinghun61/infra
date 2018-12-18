# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions.

Has "bb" prefix to avoid confusion with components.utils.
"""

from google.protobuf import struct_pb2


def dict_to_struct(d):  # pragma: no cover
  """Converts a dict to google.protobuf.Struct."""
  s = struct_pb2.Struct()
  s.update(d)
  return s


def update_struct(dest, src):  # pragma: no cover
  """Updates dest struct with values from src.

  Like dict.update, but for google.protobuf.Struct.
  """
  for key, value in src.fields.iteritems():
    # This will create a new struct_pb2.Value if one does not exist.
    dest.fields[key].CopyFrom(value)
