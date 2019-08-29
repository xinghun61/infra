# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for ast_pb2 functions."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from proto import ast_pb2
from proto import tracker_pb2


class ASTPb2Test(unittest.TestCase):

  def testCond(self):
    fd = tracker_pb2.FieldDef(field_id=1, field_name='Size')
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [fd], ['XL'], [], key_suffix='-approver')
    self.assertEqual(ast_pb2.QueryOp.EQ, cond.op)
    self.assertEqual([fd], cond.field_defs)
    self.assertEqual(['XL'], cond.str_values)
    self.assertEqual([], cond.int_values)
    self.assertEqual(cond.key_suffix, '-approver')
