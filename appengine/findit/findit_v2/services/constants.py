# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Max number of builds Findit should look back to find regression ranges.
MAX_BUILDS_TO_CHECK = 20

# Tag to indicate the purpose of a rerun build.
RERUN_BUILD_PURPOSE_TAG_KEY = 'purpose'

# Purpose of a rerun build in compile failure analysis.
COMPILE_RERUN_BUILD_PURPOSE = 'compile-failure-culprit-finding'

# Purpose of a rerun build in test failure analysis.
TEST_RERUN_BUILD_PURPOSE = 'test-failure-culprit-finding'

# Tag for the build id that is analyzed by a rerun build.
ANALYZED_BUILD_ID_TAG_KEY = 'analyzed_build_id'
