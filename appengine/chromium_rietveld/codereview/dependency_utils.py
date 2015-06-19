# Copyright 2015 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Contains utilities to help deal with the dependencies of a patchset."""

from codereview import models


DEPENDENCY_DELIMITER = ':'


def remove_dependencies_from_all_patchsets(issue):
  """Remove all dependencies from all patchsets of this issue.

  This method should be called when a CL is closed or deleted.

  Args:
    issue: (models.Issue) The issue we to remove dependencies to.
  """
  for patchset in issue.patchsets:
    remove_dependencies(patchset)


def remove_all_patchsets_as_dependents(issue):
  """Remove all patchsets of this issue as dependents.

  This method should be called when a CL is deleted.

  Args:
    issue: (models.Issue) The issue whose dependencies we want to update.
  """
  for patchset in issue.patchsets:
    remove_as_dependent(patchset)


def remove_dependencies(patchset):
  """Remove all dependencies on this patchset.

  This method should be called when a patchset is deleted.

  Args:
    patchset: (models.PatchSet) The patchset we want to remove dependencies to.
  """
  _update_dependents(patchset, remove_dependency=True)


def remove_as_dependent(patchset):
  """Remove the specified patchset as a dependent.

  This method should be called when a patchset is deleted.

  Args:
    patchset: (models.PatchSet) The patchset we want to remove as a dependent.
  """
  dependency_str = patchset.depends_on_patchset
  if not dependency_str:
    return
  depends_on_tokens = get_dependency_tokens(dependency_str)
  depends_on_issue = models.Issue.get_by_id(int(depends_on_tokens[0]))
  if not depends_on_issue:
    return
  depends_on_patchset = models.PatchSet.get_by_id(
        int(depends_on_tokens[1]), parent=depends_on_issue.key)
  if not depends_on_patchset:
    return
  if depends_on_patchset.dependent_patchsets:
    target_str = _get_dependency_str(patchset.issue_key.id(),
                                     patchset.key.id())
    if target_str in depends_on_patchset.dependent_patchsets:
      depends_on_patchset.dependent_patchsets.remove(target_str)
      depends_on_patchset.put()


def get_dependency_tokens(dependency_str):
  return dependency_str.split(DEPENDENCY_DELIMITER)


def _get_dependency_str(issue_key, patchset_key):
  return '%s%s%s' % (issue_key, DEPENDENCY_DELIMITER, patchset_key)


def _update_dependents(patchset, remove_dependency):
  if not patchset:
    return
  for dependency_str in patchset.dependent_patchsets:
    depends_on_tokens = get_dependency_tokens(dependency_str)
    dependent_issue = models.Issue.get_by_id(int(depends_on_tokens[0]))
    if not dependent_issue:
      continue
    dependent_patchset = models.PatchSet.get_by_id(
        int(depends_on_tokens[1]), parent=dependent_issue.key)
    if not dependent_patchset:
      continue
    dependent_str = _get_dependency_str(patchset.issue_key.id(),
                                        patchset.key.id())
    if remove_dependency:
      # Sanity check that the dependency_str of this patchset is what we expect
      # before we delete it.
      if dependent_patchset.depends_on_patchset == dependent_str:
        dependent_patchset.depends_on_patchset = ""
        dependent_patchset.put()
    else:
      # Sanity check that this patchset has no existing dependency before we add
      # a new one.
      if dependent_patchset.depends_on_patchset == "":
        dependent_patchset.depends_on_patchset = dependent_str
        dependent_patchset.put()


def mark_as_dependent_and_get_dependency_str(
    dependency_str, dependent_issue_key, dependent_patchset_key):
  """Marks the specified patchset as a dependent and returns its dependency str.

  Args:
    dependency_str: (str) The issue and patchset the specified patchset depends
                     on.
    dependent_issue_key: (str) The issue key of the patchset we want to mark as
                         dependent.
    dependent_patchset_key: (str) The key of the patchset we want to mark as
                            dependent.
  """
  if not dependency_str:
    return None
  depends_on_tokens = get_dependency_tokens(dependency_str)
  depends_on_issue = models.Issue.get_by_id(int(depends_on_tokens[0]))
  if not depends_on_issue:
    return None
  depends_on_patchset = models.PatchSet.get_by_id(
      int(depends_on_tokens[1]), parent=depends_on_issue.key)
  if not depends_on_patchset:
    return None

  if not depends_on_patchset.dependent_patchsets:
    depends_on_patchset.dependent_patchsets = []
  dependent_str = _get_dependency_str(dependent_issue_key,
                                      dependent_patchset_key)
  if dependent_str not in depends_on_patchset.dependent_patchsets:
    depends_on_patchset.dependent_patchsets.append(dependent_str)
  depends_on_patchset.put()

  return dependency_str

