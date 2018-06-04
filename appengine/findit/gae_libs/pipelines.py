# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module provides base pipeline classes with defined input/output types.

* SynchronousPipeline: A base pipeline class for synchronous pipelines that
  return a value immediately after some computation.

  class Info(StructuredObject):
    threshold = int
    l = list

  class FilterSum(SynchronousPipeline):
    input_type = Info
    output_type = int
    def RunImpl(self, info):
      return sum((v for v in info.l if v >= info.threshold))

  info = Info(threshold=6, l=[1, 5, 3, 7, 4, 8])
  p = FilterSum(info)
  p.start()

* GeneratorPipeline: A base pipeline class for generator piplines that spawns
  other sub-pipelines for further computation.

  class BuildInfo(StructuredObject):
    ...

  class FailureSignals(StructuredObject):
    ...

  class RegressionRange(StructuredObject):
    ...

  class AggregatedInfo(StructuredObject):
    build_info = BuildInfo
    regression_range = RegressionRange
    failure_signals = FailureSignals

  class AnalysisResult(StructuredObject):
    ...

  class ExtractFailureSignals(SynchronousPipeline):
    input_type = BuildInfo
    output_type = FailureSignals
    def RunImpl(self, info):
      ...
      return FailureSignals(...)

  class IdentifyRegressionRange(SynchronousPipeline):
    input_type = BuildInfo
    output_type = RegressionRange
    def RunImpl(self, info):
      ...
      return RegressionRange(...)

  class IdentifyCulprit(SynchronousPipeline):
    input_type = AggregatedInfo
    output_type = AnalysisResult
    def RunImpl(self, info):
      ...
      return AnalysisResult(...)

  class AnalyzeBuild(GeneratorPipeline):
    input_type = BuildInfo
    def RunImpl(self, info):
      signals = yield ExtractFailureSignals(info)
      regression_range = yield IdentifyRegressionRange(info)
      yield IdentifyCulprit(
          AggregatedInfo(build_info=info,
                         regression_range=regression_range,
                         failure_signals=signals))

* AsynchronousPipeline: A base pipeline class for asynchronous pipelines that
  depend on external data/actions, and wait for callback.

  class TestInfo(StructuredObject):
    build_info = BuildInfo
    step_name = str
    test_list = list

  class RerunTests(AsynchronousPipeline):
    input_type = TestInfo
    output_type = dict  # Map from test names to pass rates.

    def RunImpl(self, info):
      ...  # Trigger a Swarming task.

    def CallbackImpl(self, info, parameters):
      ...  # Read results from Swarming/Isolate, and compute test pass rates.
      return None, {'test': 0.80}
"""

import copy
import logging
import types

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

import pipeline as pipeline
from pipeline import handlers as pipeline_handlers
from pipeline import status_ui as pipeline_status_ui

from libs import exceptions
from libs.structured_object import StructuredObject

_UNDEFINED_TYPE = object()
_SUPPORTED_TYPES = (type(None), int, float, long, basestring, list, dict,
                    StructuredObject)
_SUPPORTED_TYPE_NAMES = ', '.join([t.__name__ for t in _SUPPORTED_TYPES])

# A randomly-generated string to indicate that pipeline parameters were encoded
# from a StructuredObject.
_ENCODED_PARAMETER_FLAG = 'ENCODED:boHH6HlAZEbA0jDg7NHrcEFIN'


# TODO(crbug.com/773340): Remove this when all pipelines are the new style.
def CreateInputObjectInstance(cls, **kwargs):
  """Returns structured object instance that accepts pipeline Future as value.

  Used as a temporary measure while we migrate our pipelines to the new style.

  Args:
    cls (class): A subclass of StructuredObject.
    kwargs (dict): A mapping from attributes to values.
  """

  def Func(_, value):
    return isinstance(value, pipeline.PipelineFuture)

  return cls(type_validation_func=Func, **kwargs)


def _ValidateType(parameter_type, parameter_name):
  """Asserts the attribute type is supported.

  Args:
    parameter_type (types.TypeType): The type of a pipeline parameter.
    parameter_name (str): The name of the parameter to be validated.
  """
  assert type(parameter_type) == types.TypeType, (
      '%s must be defined with a class or a type' % parameter_name)
  assert any(issubclass(parameter_type, t) for t in _SUPPORTED_TYPES), (
      '%s must be in supported types: %r.' % (parameter_name,
                                              _SUPPORTED_TYPE_NAMES))


def _ConvertInputObjectToPipelineParameters(input_type, args, kwargs):
  """Coverts the structured object into arguments to pass over to pipeline."""
  # In creation of the pipeline, structured input should be encoded so that
  # dependencies among pipelines will be handled properly. However, in
  # execution of the pipeline, parameters should not be encoded again.
  assert len(args) == 1, (
      'BasePipeline expects only one positional parameter, but got %d!' %
      len(args))
  if isinstance(args[0], basestring) and args[0] == _ENCODED_PARAMETER_FLAG:
    # Already encoded, return as is.
    return args, kwargs

  assert len(kwargs) == 0, 'Pipeline expects no keyword arguments!'

  if isinstance(args[0], pipeline.PipelineFuture):
    # Accept Future output of another pipeline.
    return args, kwargs

  assert isinstance(args[0],
                    input_type), ('Expected input of type %s, but got %s' %
                                  (input_type.__name__, type(args[0]).__name__))
  if not issubclass(input_type, StructuredObject):
    return args, kwargs

  return [_ENCODED_PARAMETER_FLAG], args[0].ToSerializable()


def _ConvertPipelineParametersToInputObject(input_type, args, kwargs):
  """Converts the given pipeline parameters back to a structured object."""
  assert len(args) == 1, (
      'Expected 1 positional argument, but got %d' % len(args))
  if isinstance(args[0], basestring) and args[0] == _ENCODED_PARAMETER_FLAG:
    return input_type.FromSerializable(kwargs)
  assert len(kwargs) == 0, 'Only 1 positional argument if not serialized'
  return args[0]


def _ConvertToPipelineOutput(output):
  """Converts the given output to a Json for pipeline."""
  if isinstance(output, StructuredObject):
    return output.ToSerializable()
  else:
    return output


class BasePipeline(pipeline.Pipeline):
  """Base class for the three types of pipelines below. No direct usage.

  Subclass must implement `RunImpl`, and can optionally implement `OnAbort` and
  `OnFinalized`. All the three functions have only one parameter as defined by
  the `input_type` in the subclass.
  """
  input_type = _UNDEFINED_TYPE
  output_type = _UNDEFINED_TYPE

  def IsRootPipeline(self):
    """Returns whether this pipeline is the root pipeline."""
    return self.pipeline_id == self.root_pipeline_id

  def OnAbort(self, arg):
    """Called when the pipeline is aborted.

    If it throws exceptions, `OnFinalized` won't be called.
    """
    pass

  def OnFinalized(self, arg):
    """Called when the pipeline is finalized (completed or aborted)."""
    pass

  def RunImpl(self, arg):
    """Called when the pipeline is executing with the given argument."""
    raise NotImplementedError()

  @property
  def root_pipeline_status_path(self):
    """Returns an absolute path to the status page of the root pipeline."""
    return '%s/status?root=%s&auto=false' % (self.base_path,
                                             self.root_pipeline_id)

  @property
  def pipeline_status_path(self):
    """Returns an absolute path to the status page of the current pipeline."""
    return '%s/status?root=%s&auto=false' % (self.base_path, self.pipeline_id)

  def __init__(self, *args, **kwargs):
    _ValidateType(self.input_type, '%s.input_type' % self.__class__.__name__)
    _ValidateType(self.output_type, '%s.output_type' % self.__class__.__name__)
    args, kwargs = _ConvertInputObjectToPipelineParameters(
        self.input_type, args, kwargs)
    super(BasePipeline, self).__init__(*args, **kwargs)

  def _LogStatusPath(self):
    """Logs the status path to the root pipeline and the current pipeline."""
    logging.info('Root pipeline: %s', self.root_pipeline_status_path)
    logging.info('Current pipeline: %s', self.pipeline_status_path)

  @exceptions.EnhanceMessage
  def _RunImplWrapper(self, arg):
    """Runs RunImpl to catch and process exceptions of user code."""
    return self.RunImpl(arg)

  def finalized(self):
    """Implements Pipeline.finalized and calls customized functions instead."""
    arg = _ConvertPipelineParametersToInputObject(self.input_type, self.args,
                                                  self.kwargs)
    if self.was_aborted:
      self.OnAbort(arg)
    self.OnFinalized(arg)

  def run_test(self, *args, **kwargs):  # pragma: no cover
    # This method needs to be implemented for unit tests.
    pass


class SynchronousPipeline(BasePipeline):
  """Base class for synchronous pipelines which returns a result immediately."""

  def run(self, *args, **kwargs):
    self._LogStatusPath()
    arg = _ConvertPipelineParametersToInputObject(self.input_type, args, kwargs)
    result = self._RunImplWrapper(arg)
    if not isinstance(result, self.output_type):
      raise pipeline.Abort('Expected output of type %s, but got %s' %
                           (self.output_type.__name__, type(result).__name__))
    return _ConvertToPipelineOutput(result)


class GeneratorPipeline(BasePipeline):
  """Base class for generator pipelines which spawns other pipelines."""
  # Output of a generator pipeline is the same as its last sub-pipeline.
  output_type = type(None)

  def CreateInputObjectInstance(self, cls, **kwargs):
    """Returns structured object instance that accepts pipeline Future as value.

    Args:
      cls (class): A subclass of StructuredObject.
      kwargs (dict): A mapping from attributes to values.
    """

    def Func(_, value):
      return isinstance(value, pipeline.PipelineFuture)

    return cls(type_validation_func=Func, **kwargs)

  def run(self, *args, **kwargs):
    self._LogStatusPath()
    arg = _ConvertPipelineParametersToInputObject(self.input_type, args, kwargs)
    pipeline_iter = self._RunImplWrapper(arg)
    if pipeline_iter and not isinstance(pipeline_iter, types.GeneratorType):
      raise pipeline.Abort(
          '%s did not spawn other pipelines' % self.__class__.__name__)
    next_future = None
    while pipeline_iter:
      try:
        sub_pipeline = pipeline_iter.send(next_future)
        next_future = yield sub_pipeline
      except StopIteration:
        break


class _AEPipelineCallbackInfo(ndb.Model):
  parameters = ndb.PickleProperty()
  completed = ndb.BooleanProperty(default=False)

  @classmethod
  def GetOrCreate(cls, key):
    ndb_key = ndb.Key(cls, key)
    return ndb_key.get() or cls(key=ndb_key, parameters={})


class AsynchronousPipeline(BasePipeline):
  """Base class for asynchronous pipelines waiting for external dependencies.

  Subclass should implement `CallbackImpl` besides `RunImpl`, and could use
  `SaveCallbackParameters` and `GetCallbackParameters` to save info between
  code executions.

  Subclass should implement `TimeoutSeconds` to enable a timeout callback and
  and `OnTimeout` to handle the timeout. For backward compatibility, default is
  no timeout callback which will be removed.

  NOTES:
  1. Don't use AsynchronousPipeline as the root pipeline, because a mid-flight
     asynchronous pipeline couldn't be canceled and aborted.
  2. If an asynchronous pipeline is aborted, only its root pipeline's `OnAbort`
     and `OnFinalized` will be called. The parent non-async pipeline should
     handle that instead.
  """
  async = True

  def SaveCallbackParameters(self, parameters):
    """Saves the parameters for next callback execution."""
    assert isinstance(parameters, dict), 'Callback parameters must be a dict.'
    callback_info = _AEPipelineCallbackInfo.GetOrCreate(self.pipeline_id)
    callback_info.parameters = parameters
    callback_info.put()

  def GetCallbackParameters(self):
    """Returns a copy of the saved parameters or an empty dict if not yet."""
    callback_info = _AEPipelineCallbackInfo.GetOrCreate(self.pipeline_id)
    return copy.deepcopy(callback_info.parameters)

  def CallbackImpl(self, arg, parameters):
    """This function is called upon an callback from external dependency.

    Args:
      arg (input_type): The input of the pipeline.
      parameters (dict): A mapping from names to string values of additional
          parameters.

    Returns:
      None, if external callback is still needed.
      A tuple (error_message, None), if error occurred. The message is a string.
        It will cause up to 5 retries of this callback with the same parameters.
      A tuple (None, result), if the pipeline should be set to completed with
        the given result. Result should match the defined output type.
    """
    raise NotImplementedError()

  def TimeoutSeconds(self):
    """Returns seconds to abort the pipeline if no timely callback.

    Any non-positive value is deemed as no timeout. (Default is no timeout.)
    A grace period of 5 minutes will be added upon the returned value.
    """
    return 0  # TODO: enforce a timeout after all existing pipelines migrated.

  # TODO(crbug.com/848329): investigate whether the pipeline input is needed.
  def OnTimeout(self, arg, parameters):  # pylint: disable=unused-argument
    """This function is called upon timeout without timely callback.

    Args:
      arg (input_type): The input of the pipeline.
      parameters (dict): A mapping from names to string values of the saved
          parameters.
    """
    logging.error('%s.OnTimeout called with %s after %s seconds',
                  type(self).__name__, parameters, self.TimeoutSeconds())

  def ScheduleCallbackTask(self, name=None, countdown=None, parameters=None):
    """Schedules a task to run the callback in the same target and queue.

    Use a unique task name to ensure an idempotent callback.

    Args:
      name (str): The task name to ensure only one task is scheduled.
      countdown (int): The seconds to delay the execution of the task.
      parameters (dict): Additional parameters to pass over to the callback. The
        name "_pipeline_timeout_" is reserved for internal usage.
    """
    logging.info(
        'Scheduling callback task: name=%r, countdown=%r, parameters=%r', name,
        countdown, parameters)
    parameters = parameters or {}
    callback_task = self.get_callback_task(
        name=name,
        target=self.target,  # Run at the same target/version as the pipeline.
        params=parameters,
        countdown=countdown)
    try:
      callback_task.add(queue_name=self.queue_name)  # Run in the same queue.
    except (taskqueue.TombstonedTaskError, taskqueue.TaskAlreadyExistsError):
      logging.warning('Duplicate callback task: %s', name)

  def run(self, *args, **kwargs):
    self._LogStatusPath()

    # Schedule an internal timeout callback task to clean up.
    timeout_seconds = self.TimeoutSeconds()
    if timeout_seconds > 0:
      timeout_seconds += 60 * 5  # Add a 5 minute grace period.
      self.ScheduleCallbackTask(
          name='timeout-callback-%s' % self.pipeline_id,
          countdown=timeout_seconds,
          parameters={
              '_pipeline_timeout_': '1',
          })

    arg = _ConvertPipelineParametersToInputObject(self.input_type, args, kwargs)
    result = self._RunImplWrapper(arg)
    if result is not None:
      logging.warning('%s.RunImpl should return nothing, but got a %s',
                      self.__class__.__name__,
                      type(result).__name__)

  def callback(self, **external_parameters):
    callback_info = _AEPipelineCallbackInfo.GetOrCreate(self.pipeline_id)
    if callback_info.completed:
      logging.warning('Pipeline completed in a previous callback or timeout.')
      return

    arg = _ConvertPipelineParametersToInputObject(self.input_type, self.args,
                                                  self.kwargs)
    timeouted = external_parameters.pop('_pipeline_timeout_', '') == '1'
    parameters = copy.deepcopy(callback_info.parameters)

    if timeouted:
      # There is a low risk that OnTimeout is still called after the pipeline is
      # completed: pipeline starts, run/RunImpl runs, external callback comes
      # and CallbackImpl runs & completes the pipeline with a result, timeout
      # callback task runs before the _AEPipelineCallbackInfo entity is set as
      # completed below.
      self.OnTimeout(arg, parameters)
      aborted = self.abort('Timeout after %d seconds' % self.TimeoutSeconds())
      logging.warning('%s aborted: %s', self.__class__.__name__, aborted)
    else:
      parameters.update(external_parameters)
      returned_value = self.CallbackImpl(arg, parameters)
      if returned_value is None:  # More external callback is needed.
        return

      error, result = returned_value
      if error is not None:
        # Signal Pipeline framework to retry the callback up to 5 times.
        # If failure still happened after all retries, the pipeline will be
        # cleaned up by the timeout callback task then.
        logging.error('Callback failed with error: %s', error)
        return 500, 'plain/text', error
      else:  # No error, fill output.
        if result and not isinstance(result, self.output_type):
          aborted = self.abort('Expected output of type %s, but got %s' %
                               (self.output_type.__name__,
                                type(result).__name__))
          logging.info('%s aborted: %s', self.__class__.__name__, aborted)
        else:
          # Marks the pipeline as complete with the given result.
          self.complete(_ConvertToPipelineOutput(result))

    # If the pipeline is already time-outed, aborted, or completed, try to
    # delete the scheduled timeout callback task before it runs.
    try:
      taskqueue.Queue(self.queue_name).delete_tasks_by_name(
          ['timeout-callback-%s' % self.pipeline_id])
      logging.debug('Timeout callback task deleted')
    except (taskqueue.TombstonedTaskError, taskqueue.BadTaskStateError):
      # If the timeout callback task is being executed, this will happen.
      logging.warning(
          'Could not delete timeout callback task: timeout-callback-%s',
          self.pipeline_id)
    callback_info = _AEPipelineCallbackInfo.GetOrCreate(self.pipeline_id)
    callback_info.completed = True
    callback_info.put()
