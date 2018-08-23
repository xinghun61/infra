# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from proto import common_pb2
from proto import build_pb2
from proto import rpc_pb2

from v2 import validation


class BaseTestCase(unittest.TestCase):
  func_name = None

  def validate(self, data):
    getattr(validation, self.func_name)(data)

  def assert_valid(self, data):
    self.validate(data)

  def assert_invalid(self, data, error_pattern):
    with self.assertRaisesRegexp(validation.Error, error_pattern):
      self.validate(data)


# Order of test classes must match the order of functions in validation.py

################################################################################
# Validation of common.proto messages.


class GerritChangeTests(BaseTestCase):
  func_name = 'validate_gerrit_change'

  def test_valid(self):
    msg = common_pb2.GerritChange(
        host='gerrit.example.com', change=1, patchset=1
    )
    self.assert_valid(msg)

  def test_no_host(self):
    msg = common_pb2.GerritChange(host='', change=1, patchset=1)
    self.assert_invalid(msg, r'host: required')


class GitilesCommitTests(BaseTestCase):
  func_name = 'validate_gitiles_commit'

  def test_valid(self):
    msg = common_pb2.GitilesCommit(
        host='gerrit.example.com',
        project='project',
        id='a' * 40,
        ref='refs/heads/master',
        position=1,
    )
    self.assert_valid(msg)

  def test_empty(self):
    msg = common_pb2.GitilesCommit()
    self.assert_invalid(msg, 'host: required')

  def test_host_and_project(self):
    msg = common_pb2.GitilesCommit(host='gerrit.example.com', project='project')
    self.assert_invalid(msg, 'id or ref is required')

  def test_invalid_ref(self):
    msg = common_pb2.GitilesCommit(
        host='gerrit.example.com',
        project='project',
        ref='master',
    )
    self.assert_invalid(msg, r'ref: must start with "refs/"')

  def test_invalid_id(self):
    msg = common_pb2.GitilesCommit(
        host='gerrit.example.com',
        project='project',
        id='deadbeef',
    )
    self.assert_invalid(msg, r'id: does not match r"')

  def test_position_without_ref(self):
    msg = common_pb2.GitilesCommit(
        host='gerrit.example.com',
        project='project',
        id='a' * 40,
        position=1,
    )
    self.assert_invalid(msg, r'position requires ref')


class TagsTests(BaseTestCase):

  def validate(self, data):
    validation.validate_tags(data, 'search')

  def test_valid(self):
    pairs = [common_pb2.StringPair(key='a', value='b')]
    self.assert_valid(pairs)

  def test_empty(self):
    pairs = []
    self.assert_valid(pairs)

  def test_key_has_colon(self):
    pairs = [common_pb2.StringPair(key='a:b', value='c')]
    self.assert_invalid(pairs, r'tag key "a:b" cannot have a colon')

  def test_no_key(self):
    pairs = [common_pb2.StringPair(key='', value='a')]
    self.assert_invalid(pairs, r'Invalid tag ":a": starts with ":"')


################################################################################
# Validation of build.proto messages.


class BuilderIDTests(BaseTestCase):
  func_name = 'validate_builder_id'

  def test_valid(self):
    msg = build_pb2.BuilderID(
        project='chromium', bucket='try', builder='linux-rel'
    )
    self.assert_valid(msg)

  def test_no_project(self):
    msg = build_pb2.BuilderID(project='', bucket='try', builder='linux-rel')
    self.assert_invalid(msg, r'project: required')


################################################################################
# Validation of rpc.proto messages.


class GetBuildRequestTests(BaseTestCase):
  func_name = 'validate_get_build_request'

  def test_valid_id(self):
    msg = rpc_pb2.GetBuildRequest(id=1)
    self.assert_valid(msg)

  def test_empty(self):
    msg = rpc_pb2.GetBuildRequest()
    self.assert_invalid(msg, r'id or \(builder and build_number\) are required')

  def test_valid_number(self):
    msg = rpc_pb2.GetBuildRequest(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        build_number=1,
    )
    self.assert_valid(msg)

  def test_id_and_builder(self):
    msg = rpc_pb2.GetBuildRequest(
        id=1,
        builder=build_pb2.BuilderID(project='chromium'),
    )
    self.assert_invalid(msg, r'mutually exclusive')


class SearchBuildsRequestTests(BaseTestCase):
  func_name = 'validate_search_builds_request'

  def test_valid(self):
    msg = rpc_pb2.SearchBuildsRequest(
        predicate=rpc_pb2.BuildPredicate(
            builder=build_pb2.
            BuilderID(project='chromium', bucket='try', builder='linux-rel'),
        )
    )
    self.assert_valid(msg)

  def test_empty(self):
    msg = rpc_pb2.SearchBuildsRequest()
    self.assert_valid(msg)

  def test_bad_page_size(self):
    msg = rpc_pb2.SearchBuildsRequest(
        predicate=rpc_pb2.BuildPredicate(
            builder=build_pb2.BuilderID(
                project='chromium', bucket='try', builder='linux-rel'
            ),
        ),
        page_size=-1,
    )
    self.assert_invalid(msg, r'page_size: must be not be negative')


class BuildPredicateTests(BaseTestCase):
  func_name = 'validate_build_predicate'

  def test_valid(self):
    msg = rpc_pb2.BuildPredicate(
        builder=build_pb2.
        BuilderID(project='chromium', bucket='try', builder='linux-rel')
    )
    self.assert_valid(msg)

  def test_empty(self):
    msg = rpc_pb2.BuildPredicate()
    self.assert_valid(msg)

  def test_invalid_builder_id(self):
    msg = rpc_pb2.BuildPredicate(builder=build_pb2.BuilderID())
    self.assert_invalid(msg, r'builder\.project: required')

  def test_gerrit_changes(self):
    msg = rpc_pb2.BuildPredicate(gerrit_changes=[common_pb2.GerritChange()])
    self.assert_invalid(msg, r'gerrit_changes\[0\].host: required')

  def test_invalid_tags(self):
    msg = rpc_pb2.BuildPredicate(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        tags=[common_pb2.StringPair(key='', value='')],
    )
    self.assert_invalid(msg, r'tags: Invalid tag')

  def test_two_ranges(self):
    msg = rpc_pb2.BuildPredicate(
        create_time=common_pb2.TimeRange(),
        build=rpc_pb2.BuildRange(),
    )
    self.assert_invalid(msg, r'create_time and build are mutually exclusive')

  def test_output_gitiles_commit(self):
    msg = rpc_pb2.BuildPredicate(
        output_gitiles_commit=common_pb2.GitilesCommit(
            host='gerrit.example.com',
            project='project',
            id=('a' * 40),
        ),
    )
    self.assert_valid(msg)


class PredicateOutputGitilesCommitTests(BaseTestCase):
  func_name = '_validate_predicate_output_gitiles_commit'

  def test_valid_id(self):
    msg = common_pb2.GitilesCommit(
        host='gerrit.example.com',
        project='project',
        id=('a' * 40),
    )
    self.assert_valid(msg)

  def test_valid_ref(self):
    msg = common_pb2.GitilesCommit(
        host='gerrit.example.com',
        project='project',
        ref='refs/heads/master',
    )
    self.assert_valid(msg)

  def test_valid_ref_position(self):
    msg = common_pb2.GitilesCommit(
        host='gerrit.example.com',
        project='project',
        ref='refs/heads/master',
        position=1,
    )
    self.assert_valid(msg)

  def test_unsupported_set_of_fields(self):
    variants = [
        common_pb2.GitilesCommit(),
        common_pb2.GitilesCommit(host='gerrit.example.com'),
        common_pb2.GitilesCommit(host='gerrit.example.com', project='project'),
        common_pb2.GitilesCommit(host='gerrit.example.com', id='a', ref='x'),
        common_pb2.GitilesCommit(host='gerrit.example.com', id='a', position=1),
    ]
    for msg in variants:
      self.assert_invalid(msg, r'unsupported set of fields')
