# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from google.appengine.ext import vendor


_THIS_DIR = os.path.dirname(os.path.realpath(__file__))

# Add all the first-party and thir-party libraries.
vendor.add(os.path.join(_THIS_DIR, 'first_party'))
vendor.add(os.path.join(_THIS_DIR, 'third_party'))
