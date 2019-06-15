# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class StepTypeEnum(object):
  COMPILE = 'COMPILE'
  TEST = 'TEST'
  INFRA = 'INFRA'


class FailureCategoryEnum(object):
  CONSISTENT_FAILURE = 'FAILURE'
  FLAKY_FAILURE = 'FLAKE'
  UNKNOWN = 'UNKNOWN'


class BuilderTypeEnum(object):
  # Builders for Findit to rerun.
  RERUN = 'RERUN'
  # Builders that Findit supports for failure analysis.
  SUPPORTED = 'SUPPORTED'
  # Builders that Findit doesn't support for failure analysis.
  UNSUPPORTED = 'UNSUPPORTED'