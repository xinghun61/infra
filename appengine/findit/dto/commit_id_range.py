# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs.structured_object import StructuredObject


class CommitID(StructuredObject):
  """Contains ID of a commit: currently commit_position and revision."""
  commit_position = int
  revision = basestring


class CommitIDRange(StructuredObject):
  """Represents a commit_id range to include an upper and lower bound."""
  lower = CommitID
  upper = CommitID
