# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

if not os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine'):
  # In non-production environment, protobuf and GAE have a package name conflict
  # on 'google'. This hack is to solve the conflict.
  import google
  google.__path__.insert(0,
                         os.path.join(
                             os.path.dirname(os.path.realpath(__file__)),
                             'third_party', 'google'))

from google.appengine.ext import vendor

# Add all the first-party and third-party libraries.
vendor.add(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), 'first_party'))
vendor.add(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), 'third_party'))
