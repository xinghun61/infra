# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os as _os

import infra as _infra

_build_scripts_common = _os.path.abspath(_os.path.join(
    _infra.__file__, _os.pardir, _os.pardir, _os.pardir,
    'build', 'scripts', 'common'))

__path__ = [_build_scripts_common]
