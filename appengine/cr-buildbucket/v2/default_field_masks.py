# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Default field masks for API responses."""

from google.protobuf import field_mask_pb2

from components import protoutil

from proto import build_pb2
from proto import rpc_pb2


def _build_default_field_paths(prefix=''):  # pragma: no cover
  paths = [
      'id',
      'builder',
      'number',
      'created_by',
      'create_time',
      'start_time',
      'end_time',
      'update_time',
      'status',
      'input.gitiles_commit',
      'input.gerrit_changes',
      'input.experimental',
      # TODO(nodir): add the following fields when they are defined in the
      # proto:
      # 'user_duration',
  ]
  return [prefix + p for p in paths]


# Maps a message class to default field paths.
_PATHS = {
    build_pb2.Build:
        _build_default_field_paths(),
    rpc_pb2.SearchBuildsResponse: (
        ['next_page_token'] + _build_default_field_paths('builds.*.')),
}

# Maps a message class to a protoutil.Mask.
MASKS = {
    mclass: protoutil.Mask.from_field_mask(
        field_mask_pb2.FieldMask(paths=paths), mclass.DESCRIPTOR)
    for mclass, paths in _PATHS.iteritems()
}
