# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os


# Print the "VPYTHON_VENV_ENV_STAMP_PATH" variable. This will be set by
# "vpython" process. Our test ensures that this is not set for test
# enviornments.
print 'Environment value is [%s]' % (os.getenv('VPYTHON_VENV_ENV_STAMP_PATH'),)
