# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import logging

from google.appengine.ext import ndb

from common import appengine_util
from common import chrome_dependency_fetcher
from common import constants
from common import time_util
from crash.crash_report import CrashReport
from crash.culprit import Culprit
from model import analysis_status
from model.crash.crash_config import CrashConfig

# TODO(http://crbug.com/659346): since most of our unit tests are
# FinditForFracas-specific, wrengr moved them to findit_for_chromecrash_test.py.
# However, now we're missing coverage for most of this file (due to the
# buggy way coverage is computed). Need to add a bunch of new unittests
# to get coverage back up.

# TODO: this class depends on ndb stuff, and should therefore move to
# cr-culprit-finder/service/predator as part of the big reorganization.
# This class should be renamed to avoid confustion between Findit and Predator.
# Think of a good name (e.g.'PredatorApp') for this class.
class Findit(object):
  def __init__(self, repository, pipeline_cls):
    """
    Args:
      repository (Repository): the Git repository for getting CLs to classify.
      pipeline_cls (class): the class for constructing pipelines in
        ScheduleNewAnalysis. This will almost surely be
        |crash.crash_pipeline.CrashWrapperPipeline|; but we must pass
        the class in as a parameter in order to break an import cycle.
    """
    self._repository = repository
    # TODO(http://crbug.com/659354): because self.client is volatile,
    # we need some way of updating the Azelea instance whenever the
    # config changes. How to do that cleanly?
    self._predator = None
    self._stacktrace_parser = None
    self._pipeline_cls = pipeline_cls

  # This is a class method because it should be the same for all
  # instances of this class. We can in fact call class methods on
  # instances (not just on the class itself), so we could in principle
  # get by with just this method. However, a @classmethod is treated
  # syntactically like a method, thus we'd need to have the |()| at the
  # end, unlike for a @property. Thus we have both the class method and
  # the property, in order to simulate a class property.
  @classmethod
  def _ClientID(cls): # pragma: no cover
    """Get the client id for this class.

    This class method is private. Unless you really need to access
    this method directly for some reason, you should use the |client_id|
    property instead.

    Returns:
      A string which is member of the CrashClient enumeration.
    """
    if cls is Findit:
      logging.warning('Findit is abstract, '
          'but someone constructed an instance and called _ClientID')
    else:
      logging.warning('Findit subclass %s forgot to implement _ClientID',
          cls.__name__)
    raise NotImplementedError()

  @property
  def client_id(self):
    """Get the client id from the class of this object.

    N.B., this property is static and should not be overridden."""
    return self._ClientID()

  # TODO(http://crbug.com/659354): can we remove the dependency on
  # CrashConfig entirely? It'd be better to receive method calls
  # whenever things change, so that we know the change happened (and
  # what in particular changed) so that we can update our internal state
  # as appropriate.
  @property
  def config(self):
    """Get the current value of the client config for the class of this object.

    N.B., this property is volatile and may change asynchronously.

    If the event of an error this method will return ``None``. That we do
    not return the empty dict is intentional. All of the circumstances
    which would lead to this method returning ``None`` indicate
    underlying bugs in code elsewhere. (E.g., creating instances of
    abstract classes, implementing a subclass which is not suppported by
    ``CrashConfig``, etc.) Because we return ``None``, any subsequent
    calls to ``__getitem__`` or ``get`` will raise method-missing errors;
    which serve to highlight the underlying bug. Whereas, if we silently
    returned the empty dict, then calls to ``get`` would "work" just
    fine; thereby masking the underlying bug!
    """
    return CrashConfig.Get().GetClientConfig(self.client_id)

  # TODO(http://crbug.com/644476): rename to CanonicalizePlatform or
  # something like that.
  def RenamePlatform(self, platform):
    """Remap the platform to a different one, based on the config."""
    # TODO(katesonia): Remove the default value after adding validity check to
    # config.
    return self.config.get('platform_rename', {}).get(platform, platform)

  def CheckPolicy(self, crash_data): # pylint: disable=W0613
    """Check whether this client supports analyzing the given report.

    Some clients only support analysis for crashes on certain platforms
    or channels, etc. This method checks to see whether this client can
    analyze the given crash. The default implementation on the Findit
    base class returns None for everything, so that unsupported clients
    reject everything, as expected.

    Args:
      crash_data (JSON): ??

    Returns:
      If satisfied, we return the |crash_data| which may have had some
      fields modified. Otherwise returns None.
    """
    return None

  # TODO(http://crbug.com/644476): rename this to something like
  # _NewAnalysis, since it only does the "allocation" and needs to/will
  # be followed up with _InitializeAnalysis anyways.
  def CreateAnalysis(self, crash_identifiers): # pylint: disable=W0613
    return None

  def GetAnalysis(self, crash_identifiers): # pylint: disable=W0613
    """Return the CrashAnalysis for the |crash_identifiers|, if one exists.

    Args:
      crash_identifiers (JSON): ??

    Returns:
      If a CrashAnalysis ndb.Model already exists for the
      |crash_identifiers|, then we return it. Otherwise, returns None.
    """
    return None

  # TODO(wrengr): this should be a method on CrashAnalysis, not on Findit.
  # TODO(http://crbug.com/659346): coverage tests for this class, not
  # just for FinditForFracas.
  def _InitializeAnalysis(self, model, crash_data): # pragma: no cover
    """(Re)Initialize a CrashAnalysis ndb.Model, but do not |put()| it yet.

    This method is only ever called from _NeedsNewAnalysis which is only
    ever called from ScheduleNewAnalysis. It is used for filling in the
    fields of a CrashAnalysis ndb.Model for the first time (though it
    can also be used to re-initialize a given CrashAnalysis). Subclasses
    should extend (not override) this to (re)initialize any
    client-specific fields they may have."""
    # Get rid of any previous values there may have been.
    model.Reset()

    # Set the version.
    # |handlers.crash.test.crash_handler_test.testAnalysisScheduled|
    # provides and expects this field to be called 'chrome_version',
    # whereas everyone else (e.g., in |crash.test.crash_pipeline_test|
    # the tests |testAnalysisNeededIfNoAnalysisYet|,
    # |testRunningAnalysisNoSuspectsFound|, |testRunningAnalysis|,
    # |testAnalysisNeededIfLastOneFailed|, |testRunningAnalysisWithSuspectsCls|)
    # expects it to be called 'crashed_version'. The latter is the
    # better/more general name, so the former needs to be changed in
    # order to get rid of this defaulting ugliness.
    model.crashed_version = crash_data.get('crashed_version',
        crash_data.get('chrome_version', None))

    # Set (other) common properties.
    model.stack_trace = crash_data['stack_trace']
    model.signature = crash_data['signature']
    model.platform = crash_data['platform']
    # TODO(wrengr): The only reason to have _InitializeAnalysis as a
    # method of the Findit class rather than as a method on CrashAnalysis
    # is so we can assert that crash_data['client_id'] == self.client_id.
    # So, either we should do that, or else we should move this to be
    # a method on CrashAnalysis.
    model.client_id = self.client_id
    model.regression_range = crash_data.get('regression_range', None)

    # Set progress properties.
    model.status = analysis_status.PENDING
    model.requested_time = time_util.GetUTCNow()

  @ndb.transactional
  def _NeedsNewAnalysis(self, crash_data):
    raise NotImplementedError()

  # TODO(http://crbug.com/659345): try to break the cycle re pipeline_cls.
  # TODO(http://crbug.com/659346): we don't cover anything after the
  # call to _NeedsNewAnalysis.
  def ScheduleNewAnalysis(self, crash_data,
      queue_name=constants.DEFAULT_QUEUE): # pragma: no cover
    """Create a pipeline object to perform the analysis, and start it.

    If we can detect that the analysis doesn't need to be performed
    (e.g., it was already performed, or the |crash_data| is empty so
    there's nothig we can do), then we will skip creating the pipeline
    at all.

    Args:
      crash_data (JSON): ??
      queue_name (??): the name of the AppEngine queue we should start
        the pipeline on.

    Returns:
      True if we started the pipeline; False otherwise.
    """
    # Check policy and tune arguments if needed.
    crash_data = self.CheckPolicy(crash_data)
    if crash_data is None:
      return False

    # Detect the regression range, and decide if we actually need to
    # run a new anlaysis or not.
    if not self._NeedsNewAnalysis(crash_data):
      return False

    crash_identifiers = crash_data['crash_identifiers']
    # N.B., we cannot pass |self| directly to the _pipeline_cls, because
    # it is not JSON-serializable (and there's no way to make it such,
    # since JSON-serializability is defined by JSON-encoders rather than
    # as methods on the objects being encoded).
    analysis_pipeline = self._pipeline_cls(self.client_id, crash_identifiers)
    # Attribute defined outside __init__ - pylint: disable=W0201
    analysis_pipeline.target = appengine_util.GetTargetNameForModule(
        constants.CRASH_BACKEND[self.client_id])
    analysis_pipeline.start(queue_name=queue_name)
    logging.info('New %s analysis is scheduled for %s', self.client_id,
                 repr(crash_identifiers))
    return True

  # TODO(wrengr): does the parser actually need the version, signature,
  # and platform? If not, then we should be able to just pass the string
  # to be parsed (which would make a lot more sense than passing the
  # whole model).
  # TODO(http://crbug.com/659346): coverage tests for this class, not
  # just for FinditForFracas.
  def ParseStacktrace(self, model): # pragma: no cover
    """Parse a CrashAnalysis's |stack_trace| string into a Stacktrace object.

    Args:
      model (CrashAnalysis): The model containing the stack_trace string
        to be parsed.

    Returns:
      On success, returns a Stacktrace object; on failure, returns None.
    """
    stacktrace = self._stacktrace_parser.Parse(
        model.stack_trace,
        chrome_dependency_fetcher.ChromeDependencyFetcher(
            self._repository
            ).GetDependency(
                model.crashed_version,
                model.platform),
        model.signature)
    if not stacktrace:
      logging.warning('Failed to parse the stacktrace %s', model.stack_trace)
      return None

    return stacktrace

  # TODO(wrengr): This is only called by |CrashAnalysisPipeline.run|;
  # we should be able to adjust things so that we only need to take in
  # |crash_identifiers|, or a CrashReport, rather than taking in the
  # whole model. And/or, we should just inline this there.
  # TODO(http://crbug.com/659346): coverage tests for this class, not
  # just for FinditForFracas.
  def FindCulprit(self, model): # pragma: no cover
    """Given a CrashAnalysis ndb.Model, return a Culprit."""
    stacktrace = self.ParseStacktrace(model)
    if stacktrace is None:
      return Culprit('', [], [], None, None)

    return self._predator.FindCulprit(CrashReport(
        crashed_version = model.crashed_version,
        signature = model.signature,
        platform = model.platform,
        stacktrace = stacktrace,
        regression_range = model.regression_range))
