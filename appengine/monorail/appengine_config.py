# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Configuration."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os
import sys

# Enable third-party imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'third_party'))

import httplib2
import oauth2client

from components import utils
utils.fix_protobuf_package()
