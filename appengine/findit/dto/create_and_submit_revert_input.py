# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs.structured_object import StructuredObject


class CreateAndSubmitRevertInput(StructuredObject):
  analysis_urlsafe_key = basestring
  build_key = basestring
