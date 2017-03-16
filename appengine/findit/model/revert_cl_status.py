# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Represent status of a revert CL created by Findit.
COMMITTED = 0
DUPLICATE = 1
FALSE_POSITIVE = 2


STATUS_TO_DESCRIPTION = {
    COMMITTED: 'committed',
    DUPLICATE: 'duplicate',
    FALSE_POSITIVE: 'false_positive',
}
