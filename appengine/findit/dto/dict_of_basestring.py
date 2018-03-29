# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs.structured_object import TypedDict


class DictOfBasestring(TypedDict):

  # TODO(crbug.com/806361): Support generic typed lists and dicts.
  _value_type = basestring
