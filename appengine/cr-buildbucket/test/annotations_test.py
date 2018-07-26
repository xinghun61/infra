# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from components import utils
utils.fix_protobuf_package()

from google.protobuf import text_format

from components import protoutil

from third_party import annotations_pb2

from proto import build_pb2
from test import test_util
import annotations

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


class ParseStepsTest(unittest.TestCase):
  maxDiff = None

  def test_parse_step(self):
    annotation_step = annotations_pb2.Step()
    with open(os.path.join(THIS_DIR, 'annotations.pb.txt')) as f:
      text_format.Merge(f.read(), annotation_step)

    expected = build_pb2.Build()
    with open(os.path.join(THIS_DIR, 'expected_steps.pb.txt')) as f:
      text = protoutil.parse_multiline(f.read())
      text_format.Merge(text, expected)

    parser = annotations.StepParser(
        default_logdog_host='logdog.example.com',
        default_logdog_prefix='project/prefix',
    )
    actual = build_pb2.Build(
        steps=parser.parse_substeps(annotation_step.substep)
    )

    # Compare messages as dicts.
    # assertEqual has better support for dicts than protobufs.
    self.assertEqual(
        test_util.msg_to_dict(expected), test_util.msg_to_dict(actual)
    )
