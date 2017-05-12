# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

# Libraries in third_party expect their root to be in path, so add the
# third_party dir to path.
sys.path.append(os.path.join(os.path.realpath(os.path.dirname(__file__)),
                             'third_party'))
