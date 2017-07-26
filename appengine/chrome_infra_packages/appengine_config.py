# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Custom UI tweaks for components.auth module."""

components_auth_UI_APP_NAME = 'CIPD'

from components import utils
utils.fix_protobuf_package()

# Assert that "google.protobuf" imports.
import google.protobuf
