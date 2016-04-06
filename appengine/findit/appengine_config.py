# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from google.appengine.ext import vendor

# Add all the third-party libraries.
vendor.add(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), 'third_party'))
