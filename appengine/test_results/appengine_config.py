# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Make webapp.template use django 1.2.  Quells default django warning.
from google.appengine.dist import use_library
use_library('django', '1.2')
