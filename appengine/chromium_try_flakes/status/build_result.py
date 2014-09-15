# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

# This line was copied from master/buildbot/status/builder.py.
NOT_STARTED, SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY, TRY_PENDING = range(-1, 7)

def getHumanReadableResult(result):
  """Returns an English name of a buildbot result value.
  """
  if result == NOT_STARTED:
    return 'NOT_STARTED'
  if result == SUCCESS:
    return 'SUCCESS'
  if result == WARNINGS:
    return 'WARNINGS'
  if result == FAILURE:
    return 'FAILURE'
  if result == SKIPPED:
    return 'SKIPPED'
  if result == EXCEPTION:
    return 'EXCEPTION'
  if result == RETRY:
    return 'RETRY'
  if result == TRY_PENDING:
    return 'TRY_PENDING'
  logging.info('unknown' + str(result))


def isResultSuccess(result):
  return result in [SUCCESS, WARNINGS]


def isResultFailure(result):
  return result in [FAILURE, SKIPPED, EXCEPTION, RETRY]


def isResultPending(result):
  return result in [NOT_STARTED, TRY_PENDING]
