# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict


def _GetTagsDict(raw_tags):
  """Converts tag list to a dict to make parsing it more easily.

  Args:
    raw_tags(list): A list of tags in the format as:
      ['master:chromium.win',
       'buildername:Win7 Tests (1)',
       'data:12345ea320d1',
       ...]
  Returns:
    tags(dict): A dict of tags in the format as:
    {
        'master': ['chromium.win'],
        'buildername': ['Win7 Tests (1)'],
        'data': ['12345ea320d1'],
        ...
    }
  """
  tags = defaultdict(list)
  for raw_tag in raw_tags:
    key, value = raw_tag.split(':', 1)
    tags[key].append(value)
  return tags


class SwarmingTaskData(object):
  """Represent a swarming task's data."""

  def __init__(self, item):
    self.task_id = item.get('task_id')
    self.outputs_ref = item.get('outputs_ref')
    self.tags = _GetTagsDict(item.get('tags', []))
    self.failure = item.get('failure')
    self.internal_failure = item.get('internal_failure')

  @property
  def non_internal_failure(self):
    return self.failure and not self.internal_failure

  @property
  def inputs_ref_sha(self):
    # TODO(crbug/820595): Switch to using the input_ref in the task request
    # instead.
    return self.tags.get('data')[0] if 'data' in self.tags else None
