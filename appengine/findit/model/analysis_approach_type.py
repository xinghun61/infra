# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# Represents the type of approach.
HEURISTIC = 0x00
TRY_JOB = 0x01
BOTH = 0x08

STATUS_TO_DESCRIPTION = {
    HEURISTIC: 'Heuristic',
    TRY_JOB: 'Try Job',
    BOTH: 'Both'
}
