# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.dict_of_basestring import DictOfBasestring
from libs.list_of_basestring import ListOfBasestring
from libs.structured_object import StructuredObject


class StepMetadata(StructuredObject):
  """Fields representing a step's metadata."""
  # The name of the step, without platform.
  canonical_step_name = basestring

  # Information about the bots.
  dimensions = DictOfBasestring

  # The full name of the step, including platform.
  full_step_name = basestring

  # Whether the step was run with vs without the patch.
  patched = bool

  # A list of swarming task IDs ran during the step.
  swarm_task_ids = ListOfBasestring

  # The name of the builder on the main waterfall this step was generated on.
  waterfall_buildername = basestring

  # The name of the matser on the main waterfall this step was generated on.
  waterfall_mastername = basestring
