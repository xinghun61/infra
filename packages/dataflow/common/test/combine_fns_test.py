# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import apache_beam as beam

from apache_beam.testing import test_pipeline
from apache_beam.testing import util
from dataflow.common import combine_fns


class TestCombineFns(unittest.TestCase):
  def test_convert_to_CSV_with_dicts(self):
    elements = {'a': 1, 'b': 2, 'c': 3}
    pipeline = test_pipeline.TestPipeline()
    result = (pipeline
              | beam.Create([elements, elements])
              | beam.CombineGlobally(combine_fns.ConvertToCSV())
    )
    util.assert_that(result, util.equal_to(['1,2,3\n1,2,3\n']))
    pipeline.run()

  def test_convert_to_CSV_with_lists(self):
    elements = [1, 2, 3]
    pipeline = test_pipeline.TestPipeline()
    result = (pipeline
              | beam.Create([elements, elements])
              | beam.CombineGlobally(combine_fns.ConvertToCSV())
    )
    util.assert_that(result, util.equal_to(['1,2,3\n1,2,3\n']))
    pipeline.run()

  def test_convert_to_CSV_with_header(self):
    elements = {'a': 1, 'b': 2, 'c': 3}
    header = ['a', 'b', 'c']
    pipeline = test_pipeline.TestPipeline()
    result = (pipeline
              | beam.Create([elements, elements])
              | beam.CombineGlobally(combine_fns.ConvertToCSV(header))
    )
    util.assert_that(result, util.equal_to(['a,b,c\n1,2,3\n1,2,3\n']))
    pipeline.run()
