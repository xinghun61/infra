# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

UNTRIAGED = 0
TRIAGED_INCORRECT = 1
TRIAGED_CORRECT = 2
TRIAGED_UNSURE = 3


TRIAGE_STATUS_TO_DESCRIPTION = {
    UNTRIAGED: 'Untriaged',
    TRIAGED_INCORRECT: 'Incorrect',
    TRIAGED_CORRECT: 'Correct',
    TRIAGED_UNSURE: 'Unsure',
}
