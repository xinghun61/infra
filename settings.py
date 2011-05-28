# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Django settings."""

import os

DEBUG = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')

FILE_UPLOAD_MAX_MEMORY_SIZE = 1048576  # 1 MB
