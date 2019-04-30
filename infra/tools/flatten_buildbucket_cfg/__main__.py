#!/usr/bin/env vpython

# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Flattens a buildbucket config proto."""

import sys

from google.protobuf import text_format
from infra.libs.buildbucket.proto.config import project_config_pb2
from infra.libs.buildbucket.swarming import flatten_swarmingcfg
from infra.libs.protoutil import multiline_proto


USAGE = '''Usage:
flatten_buildbucket_cfg [INPUT_FILE]

Where INPUT_FILE is a text format buildbucket config (
http://luci-config.appspot.com/schemas/projects:buildbucket.cfg)

If INPUT_FILE is "-" or is not specified, will read from standard in.'''


def _normalize_acls(acls):
  """Normalizes a RepeatedCompositeContainer of Acl messages."""
  for a in acls:
    if a.identity and ':' not in a.identity:
      a.identity = 'user:%s' % a.identity
  sort_key = lambda a: (a.role, a.group, a.identity)
  acls.sort(key=sort_key)
  for i in xrange(len(acls) - 1, 0, -1):
    if sort_key(acls[i]) == sort_key(acls[i - 1]):
      del acls[i]


def _expand_auto_builder_dimension(b):
  if (b.auto_builder_dimension == project_config_pb2.YES and
      not any(d.startswith('builder:') for d in b.dimensions)):
    b.dimensions.append('builder:%s' % b.name)
  b.auto_builder_dimension = project_config_pb2.UNSET


def _remove_noop_dimensions(b):
  """Removes dimensions that look like "<key>:", they are noop."""
  dims = list(b.dimensions)
  b.ClearField('dimensions')
  for d in dims:
    chunks = d.split(':')
    if len(chunks) != 2 or chunks[1]:
      b.dimensions.append(d)


def _move_swarming_defaults(b, swarming):
  if not b.swarming_host:
    b.swarming_host = swarming.hostname
  if (not b.HasField('task_template_canary_percentage') and
      swarming.HasField('task_template_canary_percentage')):
    b.task_template_canary_percentage.value = (
        swarming.task_template_canary_percentage.value)


def flatten(orig):
  pbtext = multiline_proto.parse_multiline(orig)
  project_cfg = project_config_pb2.BuildbucketCfg()
  text_format.Merge(pbtext, project_cfg)
  acl_sets_by_name = {a.name: a for a in project_cfg.acl_sets}
  builder_mixins_by_name = {m.name: m for m in project_cfg.builder_mixins}
  for bucket_cfg in project_cfg.buckets:
    # Inline ACL sets.
    for name in bucket_cfg.acl_sets:
      acl_set = acl_sets_by_name.get(name)
      if not acl_set:
        raise ValueError(
            'referenced acl_set not found.\n'
            'Bucket: %r\n'
            'ACL set name: %r\n', bucket_cfg.name, name
        )
      bucket_cfg.acls.extend(acl_set.acls)
    bucket_cfg.ClearField('acl_sets')
    _normalize_acls(bucket_cfg.acls)
    if bucket_cfg.HasField('swarming'):
      # Pull builder defaults out and apply default pool.
      defaults = bucket_cfg.swarming.builder_defaults
      bucket_cfg.swarming.ClearField('builder_defaults')
      if not any(d.startswith('pool:') for d in defaults.dimensions):
        defaults.dimensions.append('pool:' + bucket_cfg.name)
      for b in bucket_cfg.swarming.builders:
        flatten_swarmingcfg.flatten_builder(b, defaults, builder_mixins_by_name)
        _expand_auto_builder_dimension(b)
        _remove_noop_dimensions(b)
        _move_swarming_defaults(b, bucket_cfg.swarming)
        b.dimensions.sort()
      # These settings have been "expanded" by _move_swarming_defaults.
      bucket_cfg.swarming.ClearField('hostname')
      bucket_cfg.swarming.ClearField('task_template_canary_percentage')
      # Sort builders by name
      bucket_cfg.swarming.builders.sort(key=lambda x: x.name)
  # Sort top-level entries by name
  project_cfg.buckets.sort(key=lambda x: x.name)
  # Clear fields that have been expanded and are now irrelevant.
  project_cfg.ClearField('acl_sets')
  project_cfg.ClearField('builder_mixins')
  return text_format.MessageToString(project_cfg, as_utf8=True)


def main(argv):
  if len(argv) >= 2:
    return USAGE
  if not argv or argv[0] == '-':
    input_file = sys.stdin
  else:
    input_file = open(argv[0])
  print(flatten(input_file.read()))


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
