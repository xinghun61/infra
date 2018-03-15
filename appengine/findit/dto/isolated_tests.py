# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""An object representing a map of compiled tests to isolated shas."""

from libs.structured_object import TypedDict


class IsolatedTests(TypedDict):
  _value_type = basestring
