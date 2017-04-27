# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.culprit import Culprit


# TODO(http://crbug.com/659346): write coverage tests.
class Predator(object): # pragma: no cover
  """The Main entry point into the Predator library."""

  def __init__(self, cl_classifier, component_classifier, project_classifier):
    self.cl_classifier = cl_classifier
    self.component_classifier = component_classifier
    self.project_classifier = project_classifier

  def FindCulprit(self, report):
    """Given a CrashReport, return a Culprit."""
    suspected_cls = self.cl_classifier(report)
    assert suspected_cls is not None

    suspected_project = (
        self.project_classifier.ClassifySuspects(suspected_cls) or
        self.project_classifier.ClassifyCallStack(
            report.stacktrace.crash_stack))

    suspected_components = (
        self.component_classifier.ClassifySuspects(suspected_cls) or
        self.component_classifier.ClassifyCallStack(
            report.stacktrace.crash_stack))

    return Culprit(project=suspected_project,
                   components=suspected_components,
                   cls=suspected_cls,
                   regression_range=report.regression_range,
                   algorithm='core_algorithm')
