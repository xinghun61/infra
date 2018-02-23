# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for issue template servlets"""

import collections
import logging

from framework import authdata
from framework import framework_bizobj
from framework import framework_helpers


ParsedTemplate = collections.namedtuple(
    'ParsedTemplate', 'name, members_only, summary, summary_must_be_edited, '
    'content, status, owner_str, labels, field_val_strs, component_paths, '
    'component_required, owner_defaults_to_member')


def ParseTemplateRequest(post_data, config):
  """Parse an issue template."""

  name = post_data.get('name', '')
  members_only = (post_data.get('members_only') == 'yes')
  summary = post_data.get('summary', '')
  summary_must_be_edited = (
      post_data.get('summary_must_be_edited') == 'yes')
  content = post_data.get('content', '')
  content = framework_helpers.WordWrapSuperLongLines(content, max_cols=75)
  status = post_data.get('status', '')
  owner_str = post_data.get('owner', '')
  labels = post_data.getall('label')
  field_val_strs = collections.defaultdict(list)
  for fd in config.field_defs:
    field_value_key = 'field_value_%d' % fd.field_id
    if post_data.get(field_value_key):
      field_val_strs[fd.field_id].append(post_data[field_value_key])

  component_paths = []
  if post_data.get('components'):
    for component_path in post_data.get('components').split(','):
      if component_path.strip() not in component_paths:
        component_paths.append(component_path.strip())
  component_required = post_data.get('component_required') == 'yes'

  owner_defaults_to_member = post_data.get('owner_defaults_to_member') == 'yes'

  return ParsedTemplate(name, members_only, summary, summary_must_be_edited,
                        content, status, owner_str, labels, field_val_strs,
                        component_paths, component_required,
                        owner_defaults_to_member)
