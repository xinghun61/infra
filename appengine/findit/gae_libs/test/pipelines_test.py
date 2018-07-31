# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import re

from google.appengine.api import taskqueue
from google.appengine.ext import db  # AppEngine pipeline uses db instead of ndb

from libs.structured_object import StructuredObject
from gae_libs import pipelines
from gae_libs.pipelines import BasePipeline
from gae_libs.testcase import TestCase


class _SimpleInfo(StructuredObject):
  param = int


class _ComplexInfo(StructuredObject):
  a = int
  b = _SimpleInfo


class _ExceptionPipeline(pipelines.SynchronousPipeline):
  input_type = int
  output_type = int

  def _FunctionToTriggerExceptionIntentionally(self, arg):
    return arg / 0

  def RunImpl(self, arg):
    return self._FunctionToTriggerExceptionIntentionally(arg)


class _SynchronousPipelineWrongOutputType(pipelines.SynchronousPipeline):
  input_type = int
  output_type = dict

  def RunImpl(self, arg):
    return [arg]


class _SynchronousPipelineWithBuiltInOutputType(pipelines.SynchronousPipeline):
  input_type = int
  output_type = list

  def RunImpl(self, arg):
    return [arg]


class _SynchronousPipelineWithSimpleInfoAsOutputType(
    pipelines.SynchronousPipeline):
  input_type = int
  output_type = _SimpleInfo

  def RunImpl(self, arg):
    return _SimpleInfo(param=arg)


class _SynchronousPipelineWithComplexInfoAsInputType(
    pipelines.SynchronousPipeline):
  input_type = _ComplexInfo
  output_type = int

  def RunImpl(self, arg):
    return arg.a + arg.b.param


class _GeneratorPipelineDoesNotSpawnPipeline(pipelines.GeneratorPipeline):
  input_type = int

  def RunImpl(self, arg):
    return


class _GeneratorPipelineReturnsNonFuture(pipelines.GeneratorPipeline):
  input_type = int
  output_type = list

  def RunImpl(self, arg):
    return [arg]


class _GeneratorPipelineWithSubPipelines(pipelines.GeneratorPipeline):
  input_type = int
  output_type = _ComplexInfo

  def _ComputeRightAway(self):
    return 10000

  def RunImpl(self, arg):
    a = self._ComputeRightAway()
    b = yield _SynchronousPipelineWithSimpleInfoAsOutputType(arg)
    complex_info = self.CreateInputObjectInstance(_ComplexInfo, a=a, b=b)
    yield _SynchronousPipelineWithComplexInfoAsInputType(complex_info)


class _AsynchronousPipelineReturnAValueInRunImpl(
    pipelines.AsynchronousPipeline):
  input_type = int
  output_type = list

  def RunImpl(self, arg):
    return [arg]


class _AsynchronousPipelineWithWrongOutputType(pipelines.AsynchronousPipeline):
  input_type = int
  output_type = list

  def RunImpl(self, arg):
    self.ScheduleCallbackTask(name=self.pipeline_id, parameters={'a': arg})

  def CallbackImpl(self, arg, parameters):
    return None, parameters


class _AsynchronousPipelineNeedMoreCallback(pipelines.AsynchronousPipeline):
  input_type = int
  output_type = basestring

  def RunImpl(self, _arg):
    self.ScheduleCallbackTask(parameters={})
    self.ScheduleCallbackTask(parameters={'trigger': ''})

  def CallbackImpl(self, _arg, parameters):
    if not parameters:
      return
    return None, 'result'


class _AsynchronousPipelineCallbackError(pipelines.AsynchronousPipeline):
  input_type = int
  output_type = str

  def RunImpl(self, _arg):
    self.ScheduleCallbackTask(parameters={})

  def CallbackImpl(self, _arg, _parameters):
    return 'error message', None


class _GeneratorPipelineSpawnAsynchronousPipelineWithWrongOutputType(
    pipelines.GeneratorPipeline):
  input_type = int

  def RunImpl(self, arg):
    yield _AsynchronousPipelineWithWrongOutputType(arg)


class _AsynchronousPipelineCallback(pipelines.AsynchronousPipeline):
  input_type = int
  output_type = int

  def TimeoutSeconds(self):
    return 60

  def RunImpl(self, callback_num):
    assert callback_num in (0, 1, 2)
    assert len(self.GetCallbackParameters()) == 0
    self.SaveCallbackParameters({'p': 'v'})
    for i in range(callback_num):
      self.ScheduleCallbackTask(name='%s-callback-%d' % (self.pipeline_id, i))


class _WrapperForAsynchronousPipelineCallback(pipelines.GeneratorPipeline):
  input_type = int
  output_type = int

  def RunImpl(self, callback_num):
    yield _AsynchronousPipelineCallback(callback_num)


class _GeneratorPipelineUnwrapInput(pipelines.GeneratorPipeline):
  input_type = _SimpleInfo
  output_type = int

  def RunImpl(self, arg):
    yield _SynchronousPipelineWithBuiltInOutputType(arg.param)


class PipelinesTest(TestCase):
  app_module = pipelines.pipeline_handlers._APP

  def testAssertionForOnlyOnePositionalInputParameter(self):
    cases = [
        (['a', 'b'], {}),
        (['a'], {
            'key': 'value'
        }),
    ]
    for args, kwargs in cases:
      with self.assertRaises(AssertionError):
        pipelines._ConvertInputObjectToPipelineParameters(str, args, kwargs)

  def testNoConvertionForSinglePipelineFutureAsInputParameter(self):
    future = pipelines.pipeline.PipelineFuture(['name'])
    args, kwargs = pipelines._ConvertInputObjectToPipelineParameters(
        int, [future], {})
    self.assertListEqual([future], args)
    self.assertDictEqual({}, kwargs)

  def testInputObjectConvertedToPipelineParameters(self):
    arg = _SimpleInfo(param=1)
    args, kwargs = pipelines._ConvertInputObjectToPipelineParameters(
        _SimpleInfo, [arg], {})
    self.assertListEqual([pipelines._ENCODED_PARAMETER_FLAG], args)
    self.assertDictEqual({'param': 1}, kwargs)

  def testInputObjectConvertedToPipelineParametersOnlyOnce(self):
    args, kwargs = pipelines._ConvertInputObjectToPipelineParameters(
        _SimpleInfo, [pipelines._ENCODED_PARAMETER_FLAG], {'param': 1})
    self.assertListEqual([pipelines._ENCODED_PARAMETER_FLAG], args)
    self.assertDictEqual({'param': 1}, kwargs)

  def testAssertionForInputTypeNotMatch(self):
    with self.assertRaises(AssertionError):
      pipelines._ConvertInputObjectToPipelineParameters(int, ['a'], {})

  def testNoConvertionIfPipelineParameterNotStructuredObject(self):
    args, kwargs = pipelines._ConvertInputObjectToPipelineParameters(
        int, [1], {})
    self.assertListEqual([1], args)
    self.assertDictEqual({}, kwargs)

  def testAssertionForSinglePipelineParameterIfNotFromStructuredObject(self):
    with self.assertRaises(AssertionError):
      pipelines._ConvertPipelineParametersToInputObject(int, [1, 2], {})

  def testConvertPipelineParametersBackToInputObject(self):
    arg = pipelines._ConvertPipelineParametersToInputObject(
        _SimpleInfo, [pipelines._ENCODED_PARAMETER_FLAG], {'param': 1})
    self.assertTrue(isinstance(arg, _SimpleInfo))
    self.assertEqual(1, arg.param)

  def testAssertionNoKeyValuePipelineParameterIfNotFromStructuredObject(self):
    with self.assertRaises(AssertionError):
      pipelines._ConvertPipelineParametersToInputObject(dict, [{
          'param': 1
      }], {'key': 'value'})

  def testNoConvertionIfPipelineParameterNotFromStructuredObject(self):
    arg = pipelines._ConvertPipelineParametersToInputObject(
        dict, [{
            'param': 1
        }], {})
    self.assertDictEqual({'param': 1}, arg)

  def testInputTypeUndefined(self):

    class InputTypeUndefinedPipeline(BasePipeline):
      output_type = dict

    with self.assertRaises(AssertionError):
      InputTypeUndefinedPipeline('a')

  def testInputTypeNotAType(self):

    class InputTypeUndefinedPipeline(BasePipeline):
      input_type = 123
      output_type = dict

    with self.assertRaises(AssertionError):
      InputTypeUndefinedPipeline('a')

  def testInputTypeNotSupported(self):

    class InputTypeNotSupportedPipeline(BasePipeline):
      input_type = file
      output_type = dict

    with self.assertRaises(AssertionError):
      InputTypeNotSupportedPipeline('file')

  def testOutputTypeUndefined(self):

    class OutputTypeUndefinedPipeline(BasePipeline):
      input_type = dict

    with self.assertRaises(AssertionError):
      OutputTypeUndefinedPipeline('a')

  def testOutputTypeNotAType(self):

    class OutputTypeUndefinedPipeline(BasePipeline):
      input_type = dict
      output_type = 'a'

    with self.assertRaises(AssertionError):
      OutputTypeUndefinedPipeline('a')

  def testOutputTypeNotSupported(self):

    class UnsupportedType(object):
      pass

    class OutputTypeNotSupportedPipeline(BasePipeline):
      input_type = int
      output_type = UnsupportedType

    with self.assertRaises(AssertionError):
      OutputTypeNotSupportedPipeline(1)

  def testFormattedRetryMessage(self):
    p = _ExceptionPipeline(1)
    p.max_attempts = 1  # pylint: disable=attribute-defined-outside-init
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertTrue(p.was_aborted)
    pipeline_key = db.Key.from_path(
        pipelines.pipeline.models._PipelineRecord.kind(), p.pipeline_id)
    pipeline_record = db.get(pipeline_key)
    self.assertIsNotNone(pipeline_record)
    self.assertIsNotNone(pipeline_record.retry_message)
    message_pattern = re.compile(
        r'^ZeroDivisionError: gae_libs/test/pipelines_test.py:\d+ '
        r'\_FunctionToTriggerExceptionIntentionally \$\$ integer '
        r'division or modulo by zero$')
    match = message_pattern.match(pipeline_record.retry_message)
    self.assertIsNotNone(match)

  def testWrongOutputTypeForReultOfSynchronousPipeline(self):
    p = _SynchronousPipelineWrongOutputType(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertTrue(p.was_aborted)

  def testBuiltInTypeAsSynchronousPipelineOutput(self):
    p = _SynchronousPipelineWithBuiltInOutputType(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertFalse(p.was_aborted)
    self.assertListEqual([1], p.outputs.default.value)

  def testToSerializableableObjectAsSynchronousPipelineOutput(self):
    p = _SynchronousPipelineWithSimpleInfoAsOutputType(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertFalse(p.was_aborted)
    self.assertDictEqual({'param': 1}, p.outputs.default.value)

  def testGeneratorPipelineWithNoSubpipelines(self):
    p = _GeneratorPipelineDoesNotSpawnPipeline(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertFalse(p.was_aborted)

  def testGeneratorPipelineReturnsNonFutureValue(self):
    p = _GeneratorPipelineReturnsNonFuture(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertTrue(p.was_aborted)

  def testGeneratorPipelineWithSubPipelines(self):
    p = _GeneratorPipelineWithSubPipelines(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertFalse(p.was_aborted)
    self.assertEqual(10001, p.outputs.default.value)

  @mock.patch('logging.warning')
  def testScheduleSameCallbackTaskTwice(self, warning_func):

    def FindTaskByName(name):
      for task in self.taskqueue_stub.get_filtered_tasks():
        if task.name == name:
          return task

    p = _AsynchronousPipelineCallback(0)
    p.start(queue_name='default')
    p.ScheduleCallbackTask(
        name='unique-task-id', countdown=60, parameters={'p': 'v'})
    p.ScheduleCallbackTask(
        name='unique-task-id', countdown=60, parameters={'p': 'v'})
    warning_func.assert_called_with('Duplicate callback task: %s',
                                    'unique-task-id')
    actual_task = FindTaskByName('unique-task-id')
    self.assertIsNotNone(actual_task)
    actual_params = actual_task.extract_params()
    del actual_params['pipeline_id']
    self.assertDictEqual({'p': 'v'}, actual_params)

  def testAsynchronousPipelineWithWrongOutputType(self):
    p = _GeneratorPipelineSpawnAsynchronousPipelineWithWrongOutputType(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertTrue(p.was_aborted)

  @mock.patch('logging.warning')
  def testWarningLoggedForAsynchronousPipelineRunImplReturnAValue(
      self, warning_func):
    p = _AsynchronousPipelineReturnAValueInRunImpl(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    p.complete()
    self.assertTrue(warning_func.called)
    warning_func.assert_called()

  def testAsynchronousPipelineNeedMoreCallback(self):
    p = _AsynchronousPipelineNeedMoreCallback(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertFalse(p.was_aborted)
    self.assertEqual('result', p.outputs.default.value)

  @mock.patch('logging.error')
  def testAsynchronousPipelineCallbackError(self, error_func):
    p = _AsynchronousPipelineCallbackError(1)
    p.start()
    # In unittests, failed tasks are not retried but failed instead.
    with self.assertRaises(Exception):
      self.execute_queued_tasks()
    error_func.assert_called_with('Callback failed with error: %s',
                                  'error message')

  @mock.patch(
      'google.appengine.api.taskqueue.Queue.delete_tasks_by_name',
      side_effect=taskqueue.BadTaskStateError())
  @mock.patch.object(_AsynchronousPipelineCallback, 'CallbackImpl')
  @mock.patch.object(_AsynchronousPipelineCallback, 'OnTimeout')
  def testAsynchronousPipelineCallbackTimeout(self, mocked_OnTimeout,
                                              mocked_CallbackImpl, _):
    p = _WrapperForAsynchronousPipelineCallback(0)
    p.start()
    self.execute_queued_tasks()

    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertTrue(p.was_aborted)

    mocked_OnTimeout.assert_called_once_with(0, {'p': 'v'})
    self.assertFalse(mocked_CallbackImpl.called)

  @mock.patch.object(
      _AsynchronousPipelineCallback, 'CallbackImpl', return_value=(None, 1))
  @mock.patch.object(_AsynchronousPipelineCallback, 'OnTimeout')
  def testAsynchronousPipelineCallbackNoTimeoutOneCallback(
      self, mocked_OnTimeout, mocked_CallbackImpl):
    original_callback = _AsynchronousPipelineCallback.callback

    def Mocked_callback(*args, **kwargs):
      assert '_pipeline_timeout_' not in kwargs, 'Timeout task not deleted'
      original_callback(*args, **kwargs)

    self.mock(_AsynchronousPipelineCallback, 'callback', Mocked_callback)

    p = _WrapperForAsynchronousPipelineCallback(1)
    p.start()
    self.execute_queued_tasks()

    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertFalse(p.was_aborted)
    self.assertEqual(1, p.outputs.default.value)
    self.assertFalse(mocked_OnTimeout.called)
    mocked_CallbackImpl.assert_called_once_with(1, {'p': 'v'})

  @mock.patch.object(
      _AsynchronousPipelineCallback, 'CallbackImpl', return_value=(None, 2))
  @mock.patch.object(_AsynchronousPipelineCallback, 'OnTimeout')
  def testAsynchronousPipelineCallbackNoTimeoutDuplicateCallback(
      self, mocked_OnTimeout, mocked_CallbackImpl):
    p = _WrapperForAsynchronousPipelineCallback(2)
    p.start()
    self.execute_queued_tasks()

    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertFalse(p.was_aborted)
    self.assertEqual(2, p.outputs.default.value)
    self.assertFalse(mocked_OnTimeout.called)
    mocked_CallbackImpl.assert_called_once_with(2, {'p': 'v'})
