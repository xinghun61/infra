# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os as _os

import infra.path_hacks as _path_hacks

_depot_tools = _os.path.abspath(
    _os.path.join(_path_hacks.full_infra_path,
                  _os.pardir, 'depot_tools'))

__path__ = [_depot_tools]
