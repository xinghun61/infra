# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

UNKNOWN = 0x00

# Reliable failures.
COMPILE = 0x08
TEST = 0x10

# Flaky failures.
INFRA = 0x01
FLAKY_TEST = 0x12


def GetDescriptionForFailureType(failure_type):  # pragma: no cover.
  description = {
      UNKNOWN: 'unknown',
      INFRA: 'infra',
      COMPILE: 'compile',
      TEST: 'test',
      FLAKY_TEST: 'flake',
  }
  return description.get(failure_type, 'No description for %s' % failure_type)
