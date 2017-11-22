# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import traceback

from analysis import log_util
from analysis.culprit import Culprit
from analysis.type_enums import LogLevel


# TODO(http://crbug.com/659346): write coverage tests.
class Predator(object): # pragma: no cover
  """The Main entry point into the Predator library."""

  def __init__(self, changelist_classifier, component_classifier,
               project_classifier, log=None):
    self._log = log
    self.changelist_classifier = changelist_classifier
    self.component_classifier = component_classifier
    self.project_classifier = project_classifier
    self._SetLog()

  def _SetLog(self):
    """Makes sure that classifiers are using the same log as Predator."""
    self.changelist_classifier.SetLog(self._log)

  def _FindCulprit(self, report):
    """Given a CrashReport, return suspected project, components and cls."""
    suspected_cls = self.changelist_classifier(report)

    suspected_project = self.project_classifier.ClassifyCallStack(
        report.stacktrace.crash_stack) if report.stacktrace else ''
    suspected_project = (
        suspected_project or
        self.project_classifier.ClassifyDepPath(report.root_repo_path))

    suspected_components = self.component_classifier.ClassifyCallStack(
        report.stacktrace.crash_stack) if report.stacktrace else []
    # If there is no components find in stacktrace, try to find component from
    # the root repo, because the crash may be a component build crash.
    suspected_components = (
        suspected_components or
        self.component_classifier.ClassifyRepoUrl(report.root_repo_url))

    return suspected_project, suspected_components, suspected_cls

  def FindCulprit(self, report):
    """Finds the culprit causing the CrashReport.

    Args:
      report (CrashReport): Report contains all the information about the crash.

    Returns:
      A tuple - (success, culprit).
      success (bool): Boolean to indicate if the analysis succeeded.
      culprit (Culprit): The culprit result.
    """
    try:
      suspected_project, suspected_components, suspected_cls = (
          self._FindCulprit(report))
      return True, Culprit(project=suspected_project,
                           components=suspected_components,
                           suspected_cls=suspected_cls,
                           regression_range=report.regression_range,
                           algorithm='core_algorithm')
    except Exception as error:
      log_util.Log(self._log, error.__class__.__name__,
                   traceback.format_exc(), LogLevel.ERROR)

    return False, Culprit(project='',
                          components=[],
                          suspected_cls=[],
                          regression_range=report.regression_range,
                          algorithm='core_algorithm')
