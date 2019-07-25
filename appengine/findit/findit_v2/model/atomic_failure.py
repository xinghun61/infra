# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from findit_v2.model.gitiles_commit import Culprit
from findit_v2.model.luci_build import LuciFailedBuild


class FileInFailureLog(ndb.Model):
  """Class for a file mentioned in failure log."""

  # normalized file path.
  path = ndb.StringProperty(indexed=False)

  # Mentioned line numbers of the file in failure log.
  line_numbers = ndb.IntegerProperty(repeated=True, indexed=False)


class AtomicFailure(ndb.Model):
  """Base Class for an atom failure.

  Atom failure means failures that cannot be further divided.
  - In compile failure atom failure is a failed compile target.
  - In test failure atom failure is a failed test.

  Key to an AtomicFailure entity is
  Key(LuciFailedBuild, <build_id>, AtomicFailure, <numeric_id>(no meaning)).
  Atomic failures happened in the same build have the same parent. And they'll
  be queried together, so their identifier is not a part of the key.
  """

  # Full step name.
  step_ui_name = ndb.StringProperty()

  # Id of the build in which this atom failure occurred the first time in
  # a sequence of consecutive failed builds.
  # For example, if a test passed in build 100, and failed in builds 101 - 105,
  # then for atom failures of builds 101 - 105, their first_failed_build_id
  # will all be id of build 101.
  # First_failed_build_id can also be used to find the analysis on the
  # failure: analysis only runs for the first time failures, so using the
  # first_failed_build_id can get to the analysis.
  first_failed_build_id = ndb.IntegerProperty()

  # Id of the build in which this atom run (targets or test) was a pass and
  # since the next build, it kept not passing (can failed, not run, or end
  # with other status).
  last_passed_build_id = ndb.IntegerProperty()

  # Id of the first build forming the group.
  # Whether or how to group failures differs from project to project.
  # So this value could be empty.
  failure_group_build_id = ndb.IntegerProperty()

  # Key to the culprit commit found by rerun based analysis.
  # There should be only one culprit for each failure.
  culprit_commit_key = ndb.KeyProperty(Culprit)
  # Key to the suspected commit found by heuristic analysis.
  # There could be multiple suspects found for each failure.
  suspect_commit_key = ndb.KeyProperty(Culprit, repeated=True)

  # Optional information for heuristic analysis.
  # Mentioned files in failure log for the failure.
  files = ndb.LocalStructuredProperty(FileInFailureLog, repeated=True)

  # Arbitrary properties of the failure.
  properties = ndb.JsonProperty(compressed=True)

  @property
  def build_id(self):
    """Gets the id of the build that this failure belongs to."""
    return self.key.parent().id()

  @classmethod
  def Create(cls,
             failed_build_key,
             step_ui_name,
             first_failed_build_id=None,
             last_passed_build_id=None,
             failure_group_build_id=None,
             files=None,
             properties=None):  # pragma: no cover
    instance = cls(step_ui_name=step_ui_name, parent=failed_build_key)

    files_objs = []
    if files:
      for path, line_numbers in files.iteritems():
        files_objs.append(
            FileInFailureLog(path=path, line_numbers=line_numbers))
    instance.files = files_objs

    instance.first_failed_build_id = first_failed_build_id
    instance.last_passed_build_id = last_passed_build_id
    instance.failure_group_build_id = failure_group_build_id
    instance.properties = properties
    return instance

  @classmethod
  def GetMergedFailureKey(cls, failure_entities, referred_build_id,
                          step_ui_name, atomic_failures):

    def get_failures_by_build_id(build_id):
      """Gets failure entities by build id."""
      build_key = ndb.Key(LuciFailedBuild, build_id)
      return cls.query(ancestor=build_key).fetch()

    assert referred_build_id, (
        'Missing referred_build_id when looking for merged failure key.')
    assert isinstance(
        atomic_failures,
        (type(None), frozenset)), ('Unexpected atomic_failures type: {}'.format(
            type(atomic_failures)))

    if referred_build_id not in failure_entities:
      failure_entities[referred_build_id] = (
          get_failures_by_build_id(referred_build_id))

    for failure in failure_entities[referred_build_id]:
      if (failure.step_ui_name == step_ui_name and
          failure.GetFailureIdentifier() == atomic_failures):
        # Found the same failure in the first failed build. Uses that
        # failure's merged_failure_key or key to be the current failure's
        # merged_failure_key.
        return failure.merged_failure_key or failure.key
    return None

  def GetFailureIdentifier(self):
    """Returns the identifier for the failure within its step.

    Returns:
    (frozenset): information to identify a failure.
      - For compile failures, it'll be the output_targets.
      - For test failures, it'll be the frozenset([test_name]).

    """
    raise NotImplementedError
