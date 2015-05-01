# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# Represents status of the analysis result of a waterfall build failure.
FOUND_CORRECT = 0
FOUND_INCORRECT = 10
NOT_FOUND_INCORRECT = 20
FOUND_UNTRIAGED = 30
NOT_FOUND_UNTRIAGED = 40
NOT_FOUND_CORRECT = 50


RESULT_STATUS_TO_DESCRIPTION = {
    FOUND_CORRECT: 'Correct - Found',
    FOUND_INCORRECT: 'Incorrect - Found',
    NOT_FOUND_INCORRECT: 'Incorrect - Not Found',
    FOUND_UNTRIAGED: 'Untriaged - Found',
    NOT_FOUND_UNTRIAGED: 'Untriaged - Not Found',
    NOT_FOUND_CORRECT: 'Correct - Not Found'
}
