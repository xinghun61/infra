# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""CAS is Content Addressable Store implementation on top of Cloud Storage.

It's main focus is consistency: if an object named X is in the store (e.g.
visible by clients), then its content hash is guaranteed to be X at all times.

The protocol is optimized for uploads of small number of large and mostly unique
files. For storing large number of small files use Isolate Server instead.

We do not trust uploading clients, hashes are verified on the server side
before making an object visible.
"""

from .api import CASServiceApi
from .impl import get_backend_routes
