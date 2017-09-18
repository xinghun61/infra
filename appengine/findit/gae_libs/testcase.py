# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from testing_utils import testing

from libs.base_testcase import BaseTestCase


class TestCase(BaseTestCase, testing.AppengineTestCase):  # pragma: no cover.
  # Setup the customized queues.
  taskqueue_stub_root_path = os.path.join(
      os.path.dirname(__file__), os.path.pardir)

  def MockPipeline(self,
                   pipeline_class,
                   result,
                   expected_args,
                   expected_kwargs=None):
    """Mocks a pipeline to return a value and asserts the expected parameters.

    Deprecated(crbug.com/766383): remove after pipeline_wrapper.py is gone.

    Args:
      pipeline_class (class): The class of the pipeline to be mocked.
      result (object): The result to be returned by the pipeline.
      expected_args (list): The list of positional parameters expected by the
          pipeline.
      expected_kwargs (dict): The dict of key-value parameters expected by the
          pipeline. Default is None.
    """
    expected_kwargs = expected_kwargs or {}

    def Mocked_run(pipeline_class_instance, *args, **kwargs):
      self.assertEqual(list(args), expected_args)
      self.assertEqual(kwargs, expected_kwargs)
      if pipeline_class_instance.async:
        pipeline_class_instance.complete(result)
      return result

    self.mock(pipeline_class, 'run', Mocked_run)

  def MockSynchronousPipeline(self, pipeline_class, expected_input,
                              mocked_output):
    """Mocks a synchronous pipeline to return a output and assert the input.

    Args:
      pipeline_class (class): The class of the pipeline to be mocked.
      expected_input (object): The single input expected by the pipeline.
      mocked_output (object): The mocked result to be returned by the pipeline.
    """

    def Mocked_RunImpl(_, arg):
      self.assertEqual(expected_input, arg)
      return mocked_output

    self.mock(pipeline_class, 'RunImpl', Mocked_RunImpl)

  def MockAsynchronousPipeline(self, pipeline_class, expected_input,
                               mocked_output):
    """Mocks an asynchronous pipeline to return a output and assert the input.

    Args:
      pipeline_class (class): The class of the pipeline to be mocked.
      expected_input (object): The single input expected by the pipeline.
      mocked_output (object): The mocked result to be returned by the pipeline.
    """

    def Mocked_RunImpl(pipeline_class_instance, arg):
      self.assertEqual(expected_input, arg)
      pipeline_class_instance.Complete(mocked_output)

    self.mock(pipeline_class, 'RunImpl', Mocked_RunImpl)
