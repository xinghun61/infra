import datetime

from waterfall.test import wf_testcase
from waterfall.process_base_swarming_task_result_pipeline import (
    ProcessBaseSwarmingTaskResultPipeline)

class ProcessBaseSwarmingTaskResultPipelineTest(wf_testcase.WaterfallTestCase):
  def setUp(self):
    super(ProcessBaseSwarmingTaskResultPipelineTest, self).setUp()
    self.pipeline = ProcessBaseSwarmingTaskResultPipeline()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121
    self.step_name = 'abc_tests on platform'
    self.test_name = 'test'

  def testConvertDateTime(self):
    fmt = '%Y-%m-%dT%H:%M:%S.%f'
    time_string = '2016-02-10T18:32:06.538220'
    test_time = self.pipeline._ConvertDateTime(time_string)
    time = datetime.datetime.strptime(time_string, fmt)
    self.assertEqual(test_time, time)

  def testConvertDateTimeNone(self):
    time_string = ''
    test_time = self.pipeline._ConvertDateTime(time_string)
    self.assertIsNone(test_time)

  def testConvertDateTimefailure(self):
    with self.assertRaises(ValueError):
      self.pipeline._ConvertDateTime('abc')
