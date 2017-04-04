# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import logging

from google.appengine.ext import ndb

from common import constants
from crash.component import Component
from crash.component_classifier import ComponentClassifier
from crash.project import Project
from crash.project_classifier import ProjectClassifier
from gae_libs import appengine_util
from libs import time_util
from model import analysis_status


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

  def __init__(self, get_repository, config):
    """
    Args:
      get_repository (callable): a function from DEP urls to ``Repository``
        objects, so we can get changelogs and blame for each dep. Notably,
        to keep the code here generic, we make no assumptions about
        which subclass of ``Repository`` this function returns. Thus,
        it is up to the caller to decide what class to return and handle
        any other arguments that class may require (e.g., an http client
        for ``GitilesRepository``).
      config (ndb.CrashConfig): Config for clients and project and component
        classifiers.
    """
    self._get_repository = get_repository

    # The top_n is the number of frames we want to check to get project
    # classifications.
    projects = [Project(name, path_regexs, function_regexs, host_directories)
                for name, path_regexs, function_regexs, host_directories
                in config.project_classifier['project_path_function_hosts']]
    self._project_classifier = ProjectClassifier(
        projects, config.project_classifier['top_n'],
        config.project_classifier['non_chromium_project_rank_priority'])

    # The top_n is the number of frames we want to check to get component
    # classifications.
    components = [Component(component_name, path_regex, function_regex)
                  for path_regex, function_regex, component_name
                  in config.component_classifier['path_function_component']]
    self._component_classifier = ComponentClassifier(
        components, config.component_classifier['top_n'])

    self._config = config

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

  def _Predator(self):
    raise NotImplementedError()

  @property
  def client_id(self):
    """Get the client id from the class of this object.

    N.B., this property is static and should not be overridden."""
    return self._ClientID()

  @property
  def client_config(self):
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
    return self._config.GetClientConfig(self.client_id)

  # TODO(http://crbug.com/644476): rename to CanonicalizePlatform or
  # something like that.
  def RenamePlatform(self, platform):
    """Remap the platform to a different one, based on the config."""
    return self.client_config['platform_rename'].get(platform, platform)

  # TODO(http://crbug.com/644476): rename this to something like
  # _NewAnalysis, since it only does the "allocation" and needs to/will
  # be followed up with _InitializeAnalysis anyways.
  def CreateAnalysis(self, crash_identifiers): # pragma: no cover
    raise NotImplementedError()

  def GetAnalysis(self, crash_identifiers): # pragma: no cover
    """Returns the CrashAnalysis for the ``crash_identifiers``, if one exists.

    Args:
      crash_identifiers (JSON): key, value pairs to uniquely identify a crash.

    Returns:
      If a CrashAnalysis ndb.Model already exists for the
      ``crash_identifiers``, then we return it. Otherwise, returns None.
    """
    raise NotImplementedError()

  def GetCrashData(self, raw_crash_data): # pragma: no cover
    """Gets ``CrashData`` object for raw json crash data from clients.

    Args:
      crash_data (JSON): Json input message from clients.

    Returns:
      Parsed ``CrashData`` object.
    """
    raise NotImplementedError()

  def _CheckPolicy(self, crash_data): # pylint: disable=W0613
    """Checks whether this client supports analyzing the given report.

    Some clients only support analysis for crashes on certain platforms
    or channels, etc. This method checks to see whether this client can
    analyze the given crash. The default implementation on the Findit
    base class returns None for everything, so that unsupported clients
    reject everything, as expected.

    Args:
      crash_data (CrashData): Parsed crash data from clients.

    Returns:
      Boolean to indicate whether the crash passed the policy check.
    """
    if not self.client_config:
      logging.info('No configuration of client %s, analysis is not supported',
                   self.client_id)
      return True

    for blacklist_marker in self.client_config['signature_blacklist_markers']:
      if blacklist_marker in crash_data.signature:
        logging.info('%s signature is not supported.', blacklist_marker)
        return False

    return True

  @ndb.transactional
  def NeedsNewAnalysis(self, crash_data):
    """Checks if the crash needs new anlysis.

    If a new analysis needs to be scheduled, initialize a ``CrashAnalysis``
    model using crash_data and put it in datastore for later culprit
    analyzing.

    Args:
      crash_data (CrashData): Parsed crash data that contains all the
        information about the crash.

    Returns:
      Boolean of whether a new analysis needs to be scheduled.
    """
    # Check policy and modify the raw_crash_data as needed.
    if not self._CheckPolicy(crash_data):
      logging.info('The analysis of %s is not supported, task will not be '
                   'scheduled.', str(crash_data.identifiers))
      return False

    # Rename platform if configured.
    crash_data.platform = self.RenamePlatform(crash_data.platform)

    model = self.GetAnalysis(crash_data.identifiers)
    if (model and not model.failed and
        crash_data.regression_range == (tuple(model.regression_range)
                                        if model.regression_range else None)):
      logging.info('The analysis of %s has already been done.',
                   repr(crash_data.identifiers))
      return False

    model = model or self.CreateAnalysis(crash_data.identifiers)
    model.Initialize(crash_data)
    model.put()
    return True

  def ProcessResultForPublishing(self, result, analysis):  # pragma: no cover
    """Add Predator internal feedback_url to result."""
    result['feedback_url'] = analysis.feedback_url
    return result

  def GetPublishableResult(self, crash_identifiers, analysis):
    """Converts a culprit result into a publishable result for client.

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

    result = self.ProcessResultForPublishing(result, analysis)
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
  def FindCulprit(self, crash_report): # pragma: no cover
    """Given a ``CrashReport``, returns a ``Culprit``."""
    if crash_report.stacktrace is None:
      logging.info('Failed to parse stacktrace. '
                   'Cannot get culprit for this crash.')
      return None

    return self._Predator().FindCulprit(crash_report)
