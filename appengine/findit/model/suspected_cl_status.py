# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Represents triage result of a suspected cl.
CORRECT = 0
INCORRECT = 1
PARTIALLY_CORRECT = 2
PARTIALLY_TRIAGED = 3

CL_STATUS_TO_DESCRIPTION = {
    CORRECT: 'Correct',
    INCORRECT: 'Incorrect',
    PARTIALLY_CORRECT: 'Partially Correct',
    PARTIALLY_TRIAGED: 'Partially Triaged'
}
