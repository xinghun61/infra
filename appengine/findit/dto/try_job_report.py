# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs.structured_object import StructuredObject


class TryJobReport(StructuredObject):
  """Common info in reports of waterfall and flake try jobs."""
  # The recipe keeps track of the revisions that were checked out on the bot's
  # work directory and local git cache with the purpose of selecting a bot that
  # has the revision we want to test if possible such that we reduce the amount
  # of data that needs to be downloaded before the recipe starts performing
  # useful work.
  last_checked_out_revision = basestring
  previously_cached_revision = basestring
  previously_checked_out_revision = basestring

  # Info about the try job itself.
  # TODO(crbug.com/796428): Convert metadata to a StructuredObject.
  metadata = dict
