#!/usr/bin/env python
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

"""Tests for codereview/dependency_utils.py."""

import unittest

import setup
setup.process_args()

from codereview import models
from codereview import dependency_utils


class MockKey(object):
  def __init__(self, key_id):
    self.key_id = key_id
  def id(self):
    return self.key_id


class MockIssue(object):
  def __init__(self, key_id):
    self.key_id = key_id

  @property
  def key(self):
    return MockKey(self.key_id)


class MockPatchSet(object):
  def __init__(self, key_id, issue_key_id, dependent_patchsets,
               depends_on_patchset):
    self.key_id = key_id
    self.issue_key_id = issue_key_id
    self.dependent_patchsets = dependent_patchsets
    self.depends_on_patchset = depends_on_patchset
    self.put_called = False

  def put(self):
    self.put_called = True
  @property
  def key(self):
    return MockKey(self.key_id)
  @property
  def issue_key(self):
    return MockKey(self.issue_key_id)


class TestPatchSetDependencyUtils(unittest.TestCase):
  """Test the dependency_utils module."""

  def setUp(self):
    # Allow models.Issue.get_by_id to be monkeypatched by the tests.
    self.original_issue_get_by_id = models.Issue.get_by_id
    # Allow models.PatchSet.get_by_id to be monkeypatched by the tests.
    self.original_patchset_get_by_id = models.PatchSet.get_by_id

  def tearDown(self):
    # Undo any monkeypatching done by the tests.
    models.Issue.get_by_id = self.original_issue_get_by_id
    models.PatchSet.get_by_id = self.original_patchset_get_by_id

  def test_remove_as_dependent(self):
    # Create the patchset we will be removing as a dependent.
    patchset = MockPatchSet('40', '4', [], '3:30')

    # Make get_by_id methods return what we expect.
    def mock_issue_get_by_id():
      def _w(*args, **_kwargs):
        return MockIssue(args[1])
      return classmethod(_w)
    models.Issue.get_by_id = mock_issue_get_by_id()

    mockpatchset = MockPatchSet('30', '3', ['4:40', '1:10'], '')
    def mock_patchset_get_by_id():
      def _w(*_args, **_kwargs):
        return mockpatchset
      return classmethod(_w)
    models.PatchSet.get_by_id = mock_patchset_get_by_id()

    # Assert that dependent_patchsets of the MockpatchSet is as expected and
    # that put was called on it.
    dependency_utils.remove_as_dependent(patchset)
    self.assertEquals(['1:10'], mockpatchset.dependent_patchsets)
    self.assertTrue(mockpatchset.put_called)


  def test_remove_dependencies(self):
    # Create the patchset we will be removing dependencies of.
    dependent_patchsets = ['1:10', '2:20', '3:30']
    patchset = MockPatchSet('40', '4', dependent_patchsets, '')

    # Make get_by_id methods return what we expect.
    def mock_issue_get_by_id():
      def _w(*args, **_kwargs):
        return MockIssue(args[1])
      return classmethod(_w)
    models.Issue.get_by_id = mock_issue_get_by_id()

    mockpatchsets = []
    def mock_patchset_get_by_id():
      def _w(*args, **kwargs):
        mockpatchset = MockPatchSet(args[1], kwargs['parent'].id(), [], '4:40')
        mockpatchsets.append(mockpatchset)
        return mockpatchset
      return classmethod(_w)
    models.PatchSet.get_by_id = mock_patchset_get_by_id()

    # Assert that depends_on_patchset of the MockpatchSets are empty and that
    # put was called on them.
    dependency_utils.remove_dependencies(patchset)
    for mockpatchset in mockpatchsets:
      self.assertEquals('', mockpatchset.depends_on_patchset)
      self.assertTrue(mockpatchset.put_called)

    # Now change the depends_on_str for the dependents. Their dependency should
    # not be changed and put should not be called on them.
    mockpatchsets = []
    def mock_patchset_get_by_id():
      def _w(*args, **kwargs):
        mockpatchset = MockPatchSet(args[1], kwargs['parent'].id(), [], '4:41')
        mockpatchsets.append(mockpatchset)
        return mockpatchset
      return classmethod(_w)
    models.PatchSet.get_by_id = mock_patchset_get_by_id()
    dependency_utils.remove_dependencies(patchset)
    for mockpatchset in mockpatchsets:
      self.assertEquals('4:41', mockpatchset.depends_on_patchset)
      self.assertFalse(mockpatchset.put_called)


  def test_mark_as_dependent_and_get_dependency_str(self):
    # Make get_by_id methods return what we expect.
    def mock_issue_get_by_id():
      def _w(*args, **_kwargs):
        return MockIssue(args[1])
      return classmethod(_w)
    models.Issue.get_by_id = mock_issue_get_by_id()

    mockpatchset = MockPatchSet('40', '4', ['1:10', '2:20'], '')
    def mock_patchset_get_by_id():
      def _w(*_args, **_kwargs):
        return mockpatchset
      return classmethod(_w)
    models.PatchSet.get_by_id = mock_patchset_get_by_id()

    dependency_str = (
        dependency_utils.mark_as_dependent_and_get_dependency_str(
            '4:40', '3', '30'))
    # Since the depends on Issue and PatchSet were found the dependency str
    # should be returned.
    self.assertEquals('4:40', dependency_str)
    # Assert that the dependent_patchsets was updated and that put was called.
    self.assertEquals(['1:10', '2:20', '3:30'],
                      mockpatchset.dependent_patchsets)
    self.assertTrue(mockpatchset.put_called)

    # Make the referenced Issue be invalid and assert that a dependency str is
    # not returned and dependent_patchsets is not updated and that put is not
    # called.
    def mock_issue_get_by_id():
      def _w(*_args, **_kwargs):
        return None
      return classmethod(_w)
    models.Issue.get_by_id = mock_issue_get_by_id()
    mockpatchset = MockPatchSet('40', '4', ['1:10', '2:20'], '')
    dependency_str = (
        dependency_utils.mark_as_dependent_and_get_dependency_str(
            '4:40', '3', '30'))
    self.assertEquals(None, dependency_str)
    self.assertEquals(['1:10', '2:20'], mockpatchset.dependent_patchsets)
    self.assertFalse(mockpatchset.put_called)

    # Make the referenced Patchset be invalid and assert that a dependency str
    # is not returned.
    def mock_issue_get_by_id():
      def _w(*args, **_kwargs):
        return MockIssue(args[1])
      return classmethod(_w)
    models.Issue.get_by_id = mock_issue_get_by_id()
    def mock_patchset_get_by_id():
      def _w(*_args, **_kwargs):
        return None
      return classmethod(_w)
    models.PatchSet.get_by_id = mock_patchset_get_by_id()
    dependency_str = (
        dependency_utils.mark_as_dependent_and_get_dependency_str(
            '4:40', '3', '30'))
    self.assertEquals(None, dependency_str)


if __name__ == '__main__':
  unittest.main()

