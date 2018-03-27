# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs.structured_object import TypedList


class ListOfBasestring(TypedList):

  # TODO(crbug.com/806361): Support generic typed lists and dicts.
  _element_type = basestring
