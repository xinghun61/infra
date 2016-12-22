# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import logging

from google.appengine.ext import ndb

from common import appengine_util
from common import chrome_dependency_fetcher
from common import constants
from crash.crash_report import CrashReport
from libs import time_util
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
  def __init__(self, repository):
    """
    Args:
      repository (Repository): the Git repository for getting CLs to classify.
    """
    self._repository = repository
    # TODO(http://crbug.com/659354): because self.client is volatile,
    # we need some way of updating the Azelea instance whenever the
    # config changes. How to do that cleanly?
    self._predator = None
    self._stacktrace_parser = None

  # This is a class method because it should be the same for all
  # instances of this class. We can in fact call class methods on
  # instances (not just on the class itself), so we could in principle
  # get by with just this method. However, a @classmethod is treated
  # syntactically like a method, thus we'd need to have the ``()`` at the
  # end, unlike for a @property. Thus we have both the class method and
  # the property, in order to simulate a class property.
  @classmethod
  def _ClientID(cls): # pragma: no cover
    """Get the client id for this class.

    This class method is private. Unless you really need to access
    this method directly for some reason, you should use the ``client_id``
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
      If satisfied, we return the ``crash_data`` which may have had some
      fields modified. Otherwise returns None.
    """
    return None

  # TODO(http://crbug.com/644476): rename this to something like
  # _NewAnalysis, since it only does the "allocation" and needs to/will
  # be followed up with _InitializeAnalysis anyways.
  def CreateAnalysis(self, crash_identifiers): # pylint: disable=W0613
    return None

  def GetAnalysis(self, crash_identifiers): # pylint: disable=W0613
    """Returns the CrashAnalysis for the ``crash_identifiers``, if one exists.

    Args:
      crash_identifiers (JSON): ??

    Returns:
      If a CrashAnalysis ndb.Model already exists for the
      ``crash_identifiers``, then we return it. Otherwise, returns None.
    """
    return None

  # TODO(wrengr): this should be a method on CrashAnalysis, not on Findit.
  # TODO(http://crbug.com/659346): coverage tests for this class, not
  # just for FinditForFracas.
  def _InitializeAnalysis(self, model, crash_data): # pragma: no cover
    """(Re)Initialize a CrashAnalysis ndb.Model, but do not ``put()`` it yet.

    This method is only ever called from _NeedsNewAnalysis which is only
    ever called from ScheduleNewAnalysis. It is used for filling in the
    fields of a CrashAnalysis ndb.Model for the first time (though it
    can also be used to re-initialize a given CrashAnalysis). Subclasses
    should extend (not override) this to (re)initialize any
    client-specific fields they may have."""
    # Get rid of any previous values there may have been.
    model.Reset()

    # Set the version.
    # ``handlers.crash.test.crash_handler_test.testAnalysisScheduled``
    # provides and expects this field to be called 'chrome_version',
    # whereas everyone else (e.g., in ``crash.test.crash_pipeline_test``
    # the tests ``testAnalysisNeededIfNoAnalysisYet``,
    # ``testRunningAnalysisNoSuspectsFound``, ``testRunningAnalysis``,
    # ``testAnalysisNeededIfLastOneFailed``,
    # ``testRunningAnalysisWithSuspectsCls``) expects it to be called
    # 'crashed_version'. The latter is the better/more general name,
    # so the former needs to be changed in order to get rid of this
    # defaulting ugliness.
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

  # TODO(wrengr): does the parser actually need the version, signature,
  # and platform? If not, then we should be able to just pass the string
  # to be parsed (which would make a lot more sense than passing the
  # whole model).
  # TODO(http://crbug.com/659346): coverage tests for this class, not
  # just for FinditForFracas.
  def ParseStacktrace(self, model): # pragma: no cover
    """Parse a CrashAnalysis's ``stack_trace`` string into a Stacktrace object.

    Args:
      model (CrashAnalysis): The model containing the stack_trace string
        to be parsed.

    Returns:
      On success, returns a Stacktrace object; on failure, returns None.
    """
    # Use up-to-date ``top_n`` in self.config to filter top n frames.
    stacktrace = self._stacktrace_parser.Parse(
        model.stack_trace,
        chrome_dependency_fetcher.ChromeDependencyFetcher(
            self._repository).GetDependency(
                model.crashed_version,
                model.platform),
        model.signature, self.config.get('top_n'))
    if not stacktrace:
      logging.warning('Failed to parse the stacktrace %s', model.stack_trace)
      return None

    return stacktrace

  def ProcessResultForPublishing(self, result, key):
    """Client specific processing of result data for publishing."""
    raise NotImplementedError()

  def GetPublishableResult(self, crash_identifiers, analysis):
    """Convert a culprit result into a publishable result for client.

    Note, this function must be called by a concrete subclass of CrashAnalysis
    which implements the ProcessResultForPublishing method.

    Args:
      crash_identifiers (dict): Dict containing identifiers that can uniquely
        identify CrashAnalysis entity.
      analysis (CrashAnalysis model): Model containing culprit result and other
        analysis information.

    Returns:
      A dict of the given ``crash_identifiers``, this model's
      ``client_id``, and a publishable version of this model's ``result``.
    """
    result = copy.deepcopy(analysis.result)
    if result.get('found') and 'suspected_cls' in result:
      for cl in result['suspected_cls']:
        cl['confidence'] = round(cl['confidence'], 2)
        cl.pop('reasons', None)

    result = self.ProcessResultForPublishing(result, analysis.key.urlsafe())
    logging.info('Publish result:\n%s',
                 json.dumps(result, indent=4, sort_keys=True))
    return {
        'crash_identifiers': crash_identifiers,
        'client_id': self.client_id,
        'result': result,
    }

  # TODO(wrengr): This is only called by ``CrashAnalysisPipeline.run``;
  # we should be able to adjust things so that we only need to take in
  # ``crash_identifiers``, or a CrashReport, rather than taking in the
  # whole model. And/or, we should just inline this there.
  # TODO(http://crbug.com/659346): coverage tests for this class, not
  # just for FinditForFracas.
  def FindCulprit(self, model): # pragma: no cover
    """Given a CrashAnalysis ndb.Model, return a Culprit."""
    stacktrace = self.ParseStacktrace(model)
    if stacktrace is None:
      return None

    return self._predator.FindCulprit(CrashReport(
        crashed_version = model.crashed_version,
        signature = model.signature,
        platform = model.platform,
        stacktrace = stacktrace,
        regression_range = model.regression_range))
