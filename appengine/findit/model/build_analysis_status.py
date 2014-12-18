# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class BuildAnalysisStatus(object):
  PENDING=0
  ANALYZING=10
  ANALYZED=70
  ERROR=80
