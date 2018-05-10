# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import os

from components import utils
utils.fix_protobuf_package()

from google.protobuf import text_format
from google.protobuf import timestamp_pb2

from components import protoutil

from testing_utils import testing

from third_party import annotations_pb2

from proto import common_pb2
from proto import build_pb2
from proto import step_pb2
from v2 import steps
from test import test_util

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


class StepsTest(testing.AppengineTestCase):
  maxDiff = None

  def test_parse_step(self):
    annotation_step = annotations_pb2.Step()
    with open(os.path.join(THIS_DIR, 'annotations.pb.txt')) as f:
      text_format.Merge(f.read(), annotation_step)

    expected = build_pb2.Build()
    with open(os.path.join(THIS_DIR, 'expected_steps.pb.txt')) as f:
      text = protoutil.parse_multiline(f.read())
      text_format.Merge(text, expected)

    converter = steps.AnnotationConverter('logdog.example.com', 'prefix')
    actual = build_pb2.Build(
        steps=converter.parse_substeps(annotation_step.substep))

    # Compare messages as dicts.
    # assertEqual has better support for dicts.
    self.assertEqual(
        test_util.msg_to_dict(expected), test_util.msg_to_dict(actual))
