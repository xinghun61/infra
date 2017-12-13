# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""An object representing the location of a test."""

from libs.structured_object import StructuredObject


class TestLocation(StructuredObject):
  # The file path at which the test is located in the codebase.
  file = basestring

  # The line within the file the where test is defined.
  line = int
