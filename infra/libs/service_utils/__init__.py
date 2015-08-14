# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

if sys.platform == 'win32':  # pragma: no cover
  from . import _daemon_win32 as daemon
elif sys.platform.startswith('darwin'):  # pragma: no cover
  from . import _daemon_darwin as daemon
else:  # pragma: no cover
  from . import _daemon_linux as daemon
