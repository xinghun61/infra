# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from google.appengine.api import taskqueue

from libs.structured_object import StructuredObject
from gae_libs import pipelines
from gae_libs.pipelines import BasePipeline
from gae_libs.testcase import TestCase


class _SimpleInfo(StructuredObject):
  param = int


class _ComplexInfo(StructuredObject):
  a = int
  b = _SimpleInfo


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
    try:
      task = self.get_callback_task(params={'a': arg}, name=self.pipeline_id)
      task.add()
    except taskqueue.TombstonedTaskError:  # pragma: no branch.
      pass

  def CallbackImpl(self, arg, parameters):
    self.Complete(parameters)


class _GeneratorPipelineSpawnAsynchronousPipelineWithWrongOutputType(
    pipelines.GeneratorPipeline):
  input_type = int

  def RunImpl(self, arg):
    yield _AsynchronousPipelineWithWrongOutputType(arg)


class _AsynchronousPipelineOutputAList(pipelines.AsynchronousPipeline):
  input_type = int
  output_type = list

  def RunImpl(self, arg):
    try:
      task = self.get_callback_task(params={'a': arg}, name=self.pipeline_id)
      task.add()
    except taskqueue.TombstonedTaskError:  # pragma: no branch.
      pass

  def CallbackImpl(self, arg, parameters):
    self.Complete([int(parameters['a'])])


class _GeneratorPipelineUnwrapInput(pipelines.GeneratorPipeline):
  input_type = _SimpleInfo
  output_type = int

  def RunImpl(self, arg):
    yield _SynchronousPipelineWithBuiltInOutputType(arg.param)


class PipelinesTest(TestCase):
  app_module = pipelines.pipeline_handlers._APP

  def testModuleCreateInputObjectInstance(self):
    input_obj = pipelines.CreateInputObjectInstance(_SimpleInfo, param=1)
    self.assertEqual(input_obj.param, 1)

    p = _GeneratorPipelineUnwrapInput(input_obj)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertFalse(p.was_aborted)

  def testModuleCreateInputObjectInstanceWithWrongType(self):
    with self.assertRaises(AssertionError):
      pipelines.CreateInputObjectInstance(_SimpleInfo, param='foo')

  def testModuleCreateInputObjectInstanceWithFuture(self):
    future = pipelines.pipeline.PipelineFuture([1])
    input_obj = pipelines.CreateInputObjectInstance(_SimpleInfo, param=future)
    input_obj_dict = input_obj.ToSerializable()
    self.assertTrue('param' in input_obj_dict)
    self.assertEqual(input_obj_dict['param'], future)

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

  def testAsynchronousPipelineWithWrongOutputType(self):
    p = _GeneratorPipelineSpawnAsynchronousPipelineWithWrongOutputType(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertTrue(p.was_aborted)

  def testAsynchronousPipelineOutputAList(self):
    p = _AsynchronousPipelineOutputAList(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    self.assertFalse(p.was_aborted)
    self.assertListEqual([1], p.outputs.default.value)

  @mock.patch('logging.warning')
  def testWarningLoggedForAsynchronousPipelineRunImplReturnAValue(
      self, warning_func):
    p = _AsynchronousPipelineReturnAValueInRunImpl(1)
    p.start()
    self.execute_queued_tasks()
    p = pipelines.pipeline.Pipeline.from_id(p.pipeline_id)
    p.complete()
    warning_func.assert_called()
