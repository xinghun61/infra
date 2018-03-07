# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class UnsupportedBuild(Exception):
  """A build cannot be converted to v2 format."""


class MalformedBuild(Exception):
  """A build has unexpected format."""


class StepFetchError(Exception):
  """Failed to fetch steps from LogDog."""
