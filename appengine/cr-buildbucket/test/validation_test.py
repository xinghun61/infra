# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock
import os
import unittest

from google.protobuf import field_mask_pb2
from google.protobuf import struct_pb2
from google.protobuf import text_format
from parameterized import parameterized

from proto import build_pb2
from proto import common_pb2
from proto import notification_pb2
from proto import rpc_pb2
from proto import step_pb2

import validation

status_name = common_pb2.Status.Name

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


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
    self.assert_invalid(msg, 'ref: required')

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
        ref='refs/heads/master',
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
    with self.assertRaisesRegexp(validation.Error, r'position: requires ref'):
      validation.validate_gitiles_commit(msg, require_ref=False)

  def test_id_or_ref(self):
    msg = common_pb2.GitilesCommit(
        host='gerrit.example.com',
        project='project',
    )
    with self.assertRaisesRegexp(validation.Error, r'id or ref is required'):
      validation.validate_gitiles_commit(msg, require_ref=False)


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

  def test_invalid_project(self):
    msg = build_pb2.BuilderID(
        project='Chromium', bucket='try', builder='linux-rel'
    )
    self.assert_invalid(msg, r'project: invalid')

  def test_invalid_bucket(self):
    msg = build_pb2.BuilderID(
        project='chromium', bucket='a b', builder='linux-rel'
    )
    self.assert_invalid(
        msg, r'bucket: Bucket name "a b" does not match regular'
    )

  def test_v1_bucket(self):
    msg = build_pb2.BuilderID(
        project='chromium', bucket='luci.chromium.ci', builder='linux-rel'
    )
    self.assert_invalid(
        msg,
        (
            r'bucket: invalid usage of v1 bucket format in v2 API; '
            'use u\'ci\' instead'
        ),
    )

  def test_invalid_builder(self):
    msg = build_pb2.BuilderID(project='chromium', bucket='try', builder='#')
    self.assert_invalid(msg, r'builder: invalid char\(s\)')


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
            builder=build_pb2.BuilderID(
                project='chromium',
                bucket='try',
                builder='linux-rel',
            ),
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


class ScheduleBuildRequestTests(BaseTestCase):
  func_name = 'validate_schedule_build_request'

  def test_valid(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=dict(project='chromium', bucket='try', builder='linux-rel'),
        gitiles_commit=dict(
            host='gerrit.example.com',
            project='project',
            id='a' * 40,
            ref='refs/heads/master',
            position=1,
        ),
        gerrit_changes=[
            dict(host='gerrit.example.com', change=1, patchset=1),
            dict(host='gerrit.example.com', change=2, patchset=2),
        ],
        tags=[
            dict(key='a', value='a1'),
            dict(key='a', value='a2'),
            dict(key='b', value='b1'),
        ],
        dimensions=[
            dict(key='d1', value='dv1'),
            dict(key='d2', value='dv2'),
        ],
        priority=100,
        notify=dict(
            pubsub_topic='projects/project_id/topics/topic_id',
            user_data='blob',
        ),
    )
    msg.properties.update({'a': 1, '$recipe_engine/runtime': {'b': 1}})
    self.assert_valid(msg)

  def test_empty_property_value(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=dict(project='chromium', bucket='try', builder='linux-rel'),
        properties=dict(fields=dict(a=struct_pb2.Value())),
    )
    self.assert_invalid(
        msg, r'properties\.a: value is not set; for null, initialize null_value'
    )

  def test_repeating_dimension_key_and_expiration(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=dict(project='chromium', bucket='try', builder='linux-rel'),
        dimensions=[
            dict(key='a', value='b'),
            dict(key='a', value='b'),
        ],
    )
    self.assert_invalid(
        msg, r'dimensions: key "a" and expiration 0s are not unique'
    )

  def test_expiration_not_suported(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=dict(project='chromium', bucket='try', builder='linux-rel'),
        dimensions=[
            dict(key='a', value='b', expiration=dict(seconds=10)),
        ],
    )
    self.assert_invalid(msg, r'dimensions\[0\]\.expiration: not supported')

  def test_no_builder_and_template_build_id(self):
    msg = rpc_pb2.ScheduleBuildRequest()
    self.assert_invalid(msg, 'builder or template_build_id is required')

  def test_no_builder_but_template_build_id(self):
    msg = rpc_pb2.ScheduleBuildRequest(template_build_id=1)
    self.assert_valid(msg)

  def test_incomplete_builder(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=build_pb2.BuilderID(project='chromium', bucket='try'),
    )
    self.assert_invalid(msg, 'builder.builder: required')

  def test_reserved_properties(self):
    properties = [
        {'buildbucket': 1},
        {'buildername': 1},
        {'$recipe_engine/runtime': {'is_luci': 1}},
        {'$recipe_engine/runtime': {'is_experimental': 1}},
    ]
    for p in properties:
      msg = rpc_pb2.ScheduleBuildRequest(
          builder=build_pb2.BuilderID(
              project='chromium', bucket='try', builder='linux-rel'
          ),
      )
      msg.properties.update(p)
      self.assert_invalid(msg, r'property .+ is reserved')

  def test_gitiles_commit_incomplete(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        gitiles_commit=common_pb2.GitilesCommit(
            host='gerrit.example.com', project='project'
        ),
    )
    self.assert_invalid(msg, r'gitiles_commit\.ref: required')

  def test_gerrit_change(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        gerrit_changes=[
            common_pb2.GerritChange(host='gerrit.example.com', change=2),
        ],
    )
    self.assert_invalid(msg, r'gerrit_changes\[0\]\.patchset: required')

  def test_tags(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        tags=[dict()]
    )
    self.assert_invalid(msg, r'tags: Invalid tag ":": starts with ":"')

  def test_dimensions(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        dimensions=[dict()]
    )
    self.assert_invalid(msg, r'dimensions\[0\]\.key: required')

  def test_priority(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        priority=256,
    )
    self.assert_invalid(msg, r'priority: must be in \[0, 255\]')

  def test_notify_pubsub_topic(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        notify=notification_pb2.NotificationConfig(),
    )
    self.assert_invalid(msg, r'notify.pubsub_topic: required')

  def test_notify_user_data(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        notify=notification_pb2.NotificationConfig(
            pubsub_topic='x',
            user_data='a' * 5000,
        ),
    )
    self.assert_invalid(msg, r'notify.user_data: must be <= 4096 bytes')

  def test_cipd_version_latest(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        exe=dict(cipd_version='latest'),
    )
    self.assert_valid(msg)

  def test_cipd_version_invalid(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        exe=dict(cipd_version=':'),
    )
    self.assert_invalid(msg, r'exe.cipd_version: invalid version ":"')

  def test_cipd_package(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        exe=dict(cipd_package='something'),
    )
    self.assert_invalid(msg, r'exe.cipd_package: disallowed')


class CancelBuildRequestTests(BaseTestCase):
  func_name = 'validate_cancel_build_request'

  def test_valid(self):
    msg = rpc_pb2.CancelBuildRequest(id=1, summary_markdown='unnecessary')
    self.assert_valid(msg)

  def test_no_build(self):
    msg = rpc_pb2.CancelBuildRequest(summary_markdown='unnecessary')
    self.assert_invalid(msg, 'id: required')

  @mock.patch('validation.MAX_BUILD_SUMMARY_MARKDOWN_SIZE', 10)
  def test_big_summary(self):
    msg = rpc_pb2.CancelBuildRequest(
        id=1, summary_markdown='a very long string'
    )
    self.assert_invalid(
        msg, r'summary_markdown: too big to accept \(18 > 10 bytes\)'
    )


class UpdateBuildRequestTests(BaseTestCase):
  func_name = 'validate_update_build_request'

  @staticmethod
  def _mk_req(paths, **build_fields):
    build_fields.setdefault('id', 1)
    return rpc_pb2.UpdateBuildRequest(
        build=build_fields, update_mask=field_mask_pb2.FieldMask(paths=paths)
    )

  def test_valid(self):
    # Comprehensive validity test. Some specific cases are covered later.
    build = build_pb2.Build()
    with open(os.path.join(THIS_DIR, 'steps.pb.txt')) as f:
      text_format.Merge(f.read(), build)
    msg = self._mk_req(
        ['build.status', 'build.steps', 'build.output.gitiles_commit'],
        status=common_pb2.SUCCESS,
        steps=build.steps,
        output=dict(
            gitiles_commit=dict(
                host='gerrit.example.com',
                project='project',
                ref='refs/heads/master',
                id='a' * 40,
                position=1,
            ),
        ),
    )
    self.assert_valid(msg)

  def test_unsupported_paths(self):
    msg = self._mk_req(['build.input'])
    self.assert_invalid(
        msg, r'update_mask\.paths: unsupported path\(s\) .+build\.input.+'
    )

  def test_empty_property_value(self):
    msg = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(
            id=1,
            output=dict(properties=dict(fields=dict(a=struct_pb2.Value()))),
        ),
        update_mask=field_mask_pb2.FieldMask(paths=['build.output.properties']),
    )
    self.assert_invalid(
        msg, r'build\.output\.properties\.a: value is not set; '
        'for null, initialize null_value'
    )

  @mock.patch('model.BuildSteps.MAX_STEPS_LEN', 10)
  def test_steps_too_big(self):
    msg = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(
            id=1,
            steps=[
                step_pb2.Step(name='x' * 1000, status=common_pb2.SCHEDULED),
            ]
        ),
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )
    self.assert_invalid(msg, r'build\.steps: too big to accept')

  @mock.patch('validation.MAX_BUILD_SUMMARY_MARKDOWN_SIZE', 10)
  def test_summary_markdown_too_big(self):
    msg = self._mk_req(
        ['build.summary_markdown'],
        summary_markdown='a very long string',
    )
    self.assert_invalid(
        msg, r'build\.summary_markdown: too big to accept \(18 > 10 bytes\)'
    )

  def test_set_scheduled_status(self):
    msg = self._mk_req(['build.status'], status=common_pb2.SCHEDULED)
    self.assert_invalid(
        msg, r'build\.status: invalid status SCHEDULED for UpdateBuild'
    )


class ValidateStepsTests(BaseTestCase):
  func_name = 'validate_steps'

  def _testcase_func_name(testcase_func, _param_num, param):  # pylint: disable=no-self-argument
    # Helper to get parameterized function name given statuses as elements in
    # parameterized tuple. Works for up to two (parent, child) steps.
    return '%s_%s' % (
        testcase_func.__name__,  # pylint: disable=no-member
        '_'.join([status_name(arg) for arg in param.args[:2]])
    )

  def test_duplicate_step_names(self):
    steps = [
        step_pb2.Step(name='foo', status=common_pb2.SCHEDULED),
        step_pb2.Step(name='bar', status=common_pb2.SCHEDULED),
        step_pb2.Step(name='foo', status=common_pb2.SCHEDULED),
    ]
    self.assert_invalid(steps, 'duplicate: u\'foo\'')

  def test_unspecified_status(self):
    steps = [
        step_pb2.Step(name='foo', status=common_pb2.SCHEDULED),
        step_pb2.Step(name='bar'),
    ]
    self.assert_invalid(
        steps, 'must have buildbucket.v2.Status that is not STATUS_UNSPECIFIED'
    )

  def test_nonexistent_status(self):
    steps = [
        step_pb2.Step(name='foo', status=3),
    ]
    self.assert_invalid(
        steps, 'must have buildbucket.v2.Status that is not STATUS_UNSPECIFIED'
    )

  def test_start_time_with_unstarted_status(self):
    steps = [
        step_pb2.Step(name='foo', status=common_pb2.SCHEDULED),
    ]
    steps[0].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
    self.assert_invalid(steps, 'invalid for status SCHEDULED')

  @parameterized.expand([
      (common_pb2.STARTED,),
      (common_pb2.SUCCESS,),
      (common_pb2.FAILURE,),
  ])
  def test_started_status_without_start_time(self, status):
    steps = [
        step_pb2.Step(name='foo', status=status),
    ]
    self.assert_invalid(
        steps, 'start_time: required by status %s' % status_name(status)
    )

  def test_nonterminal_status_with_end_time(self):
    steps = [
        step_pb2.Step(name='foo', status=common_pb2.STARTED),
    ]
    steps[0].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
    steps[0].end_time.FromDatetime(datetime.datetime(2019, 1, 1))
    self.assert_invalid(
        steps, 'must have both or neither end_time and a terminal status'
    )

  @parameterized.expand([
      (common_pb2.SUCCESS,),
      (common_pb2.FAILURE,),
      (common_pb2.INFRA_FAILURE,),
      (common_pb2.CANCELED,),
  ])
  def test_terminal_status_without_end_time(self, status):
    steps = [
        step_pb2.Step(name='foo', status=status),
    ]
    steps[0].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
    self.assert_invalid(
        steps, 'must have both or neither end_time and a terminal status'
    )

  @parameterized.expand([
      (common_pb2.SUCCESS,),
      (common_pb2.FAILURE,),
      (common_pb2.INFRA_FAILURE,),
      (common_pb2.CANCELED,),
  ])
  def test_step_start_after_end(self, status):
    steps = [
        step_pb2.Step(name='foo', status=status),
    ]
    steps[0].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
    steps[0].end_time.FromDatetime(datetime.datetime(2017, 1, 1))
    self.assert_invalid(steps, 'start_time after end_time')

  def test_missing_steps_shallow(self):
    steps = [
        step_pb2.Step(name='a|b', status=common_pb2.SCHEDULED),
    ]
    self.assert_invalid(steps, r'parent to u\'a\|b\' must precede')

  def test_missing_steps_deep(self):
    steps = [
        step_pb2.Step(name='a', status=common_pb2.STARTED),
        step_pb2.Step(name='a|b', status=common_pb2.STARTED),
        step_pb2.Step(name='a|b|c', status=common_pb2.STARTED),
        step_pb2.Step(name='a|b|c|d|e', status=common_pb2.STARTED),
    ]
    for i in range(4):
      steps[i].start_time.FromDatetime(datetime.datetime(2018, 1, 1))

    self.assert_invalid(steps, r'parent to u\'a\|b\|c\|d\|e\' must precede')

  def test_unstarted_parent(self):
    steps = [
        step_pb2.Step(name='a', status=common_pb2.SCHEDULED),
        step_pb2.Step(name='a|b', status=common_pb2.SCHEDULED),
    ]
    self.assert_invalid(steps, 'parent u\'a\' must be at least STARTED')

  @parameterized.expand(
      [
          (common_pb2.SCHEDULED, common_pb2.SUCCESS, False),
          (common_pb2.SCHEDULED, common_pb2.FAILURE, False),
          (common_pb2.SCHEDULED, common_pb2.INFRA_FAILURE, False),
          (common_pb2.SCHEDULED, common_pb2.CANCELED, False),
          (common_pb2.STARTED, common_pb2.SUCCESS, True),
          (common_pb2.STARTED, common_pb2.FAILURE, True),
          (common_pb2.STARTED, common_pb2.INFRA_FAILURE, True),
          (common_pb2.STARTED, common_pb2.CANCELED, True),
      ],
      testcase_func_name=_testcase_func_name,
  )
  def test_nonterminal_with_terminal_parent(self, child, parent, needs_start):
    steps = [
        step_pb2.Step(name='a', status=parent),
        step_pb2.Step(name='a|b', status=common_pb2.SUCCESS),
        step_pb2.Step(name='a|c', status=child),
    ]
    for i in range(3):
      if i < 2 or needs_start:
        steps[i].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
      if i < 2:
        steps[i].end_time.FromDatetime(datetime.datetime(2019, 1, 1))

    self.assert_invalid(
        steps,
        r'non-terminal \(%s\) u\'a\|c\' must have STARTED parent u\'a\' \(%s\)'
        % (status_name(child), status_name(parent))
    )

  @parameterized.expand(
      [
          (common_pb2.FAILURE, common_pb2.SUCCESS),
          (common_pb2.INFRA_FAILURE, common_pb2.FAILURE),
          (common_pb2.CANCELED, common_pb2.INFRA_FAILURE),
      ],
      testcase_func_name=_testcase_func_name,
  )
  def test_parent_status_better_than_child(self, child, parent):
    steps = [
        step_pb2.Step(name='a', status=common_pb2.CANCELED),
        step_pb2.Step(name='a|b', status=common_pb2.CANCELED),
        step_pb2.Step(name='a|b|c', status=common_pb2.SUCCESS),
        step_pb2.Step(name='a|b|c|d', status=common_pb2.SUCCESS),
        step_pb2.Step(name='a|b|e', status=parent),
        step_pb2.Step(name='a|b|e|f', status=child),
        step_pb2.Step(name='a|b|e|f|g', status=common_pb2.SUCCESS),
        step_pb2.Step(name='a|b|e|f|h', status=common_pb2.SUCCESS),
    ]
    for i in range(8):
      steps[i].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
      steps[i].end_time.FromDatetime(datetime.datetime(2019, 1, 1))

    self.assert_invalid(
        steps,
        r'u\'a\|b\|e\|f\'\'s status %s is worse than parent u\'a\|b\|e\'\'s '
        'status %s' % (status_name(child), status_name(parent))
    )

  @parameterized.expand(
      [
          (common_pb2.SUCCESS, common_pb2.STARTED, False),
          (common_pb2.FAILURE, common_pb2.STARTED, False),
          (common_pb2.INFRA_FAILURE, common_pb2.STARTED, False),
          (common_pb2.CANCELED, common_pb2.STARTED, False),
          (common_pb2.SUCCESS, common_pb2.FAILURE, True),
          (common_pb2.FAILURE, common_pb2.INFRA_FAILURE, True),
          (common_pb2.INFRA_FAILURE, common_pb2.CANCELED, True),
      ],
      testcase_func_name=_testcase_func_name,
  )
  def test_consistent_statuses(self, child, parent, needs_end):
    steps = [
        step_pb2.Step(name='a', status=common_pb2.STARTED),
        step_pb2.Step(name='a|b', status=common_pb2.STARTED),
        step_pb2.Step(name='a|b|c', status=common_pb2.STARTED),
        step_pb2.Step(name='a|b|c|d', status=common_pb2.STARTED),
        step_pb2.Step(name='a|b|e', status=parent),
        step_pb2.Step(name='a|b|e|f', status=child),
        step_pb2.Step(name='a|b|e|f|g', status=common_pb2.SUCCESS),
        step_pb2.Step(name='a|b|e|f|h', status=common_pb2.SUCCESS),
    ]
    for i in range(8):
      steps[i].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
      if i > 4 or (i == 4 and needs_end):
        steps[i].end_time.FromDatetime(datetime.datetime(2019, 1, 1))

    self.assert_valid(steps)

  def test_start_before_parent_start(self):
    steps = [
        step_pb2.Step(name='a', status=common_pb2.SUCCESS),
        step_pb2.Step(name='a|b', status=common_pb2.SUCCESS),
    ]
    steps[0].start_time.FromDatetime(datetime.datetime(2019, 1, 1))
    steps[0].end_time.FromDatetime(datetime.datetime(2019, 2, 1))
    steps[1].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
    steps[1].end_time.FromDatetime(datetime.datetime(2018, 2, 1))

    self.assert_invalid(
        steps, r'start_time: cannot precede parent u\'a\'\'s start time'
    )

  def test_start_after_parent_end(self):
    steps = [
        step_pb2.Step(name='a', status=common_pb2.FAILURE),
        step_pb2.Step(name='a|b', status=common_pb2.FAILURE),
    ]
    steps[0].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
    steps[0].end_time.FromDatetime(datetime.datetime(2018, 2, 1))
    steps[1].start_time.FromDatetime(datetime.datetime(2019, 1, 1))
    steps[1].end_time.FromDatetime(datetime.datetime(2019, 2, 1))

    self.assert_invalid(
        steps, r'start_time: cannot follow parent u\'a\'\'s end time'
    )

  def test_end_before_parent_start(self):
    steps = [
        step_pb2.Step(name='a', status=common_pb2.INFRA_FAILURE),
        step_pb2.Step(name='a|b', status=common_pb2.INFRA_FAILURE),
    ]
    steps[0].start_time.FromDatetime(datetime.datetime(2019, 1, 1))
    steps[0].end_time.FromDatetime(datetime.datetime(2019, 2, 1))
    steps[1].end_time.FromDatetime(datetime.datetime(2018, 2, 1))

    self.assert_invalid(
        steps, r'end_time: cannot precede parent u\'a\'\'s start time'
    )

  def test_end_after_parent_end(self):
    steps = [
        step_pb2.Step(name='a', status=common_pb2.FAILURE),
        step_pb2.Step(name='a|b', status=common_pb2.FAILURE),
    ]
    steps[0].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
    steps[0].end_time.FromDatetime(datetime.datetime(2019, 1, 1))
    steps[1].start_time.FromDatetime(datetime.datetime(2018, 2, 1))
    steps[1].end_time.FromDatetime(datetime.datetime(2019, 2, 1))

    self.assert_invalid(
        steps, r'end_time: cannot follow parent u\'a\'\'s end time'
    )

  @parameterized.expand(
      [
          (common_pb2.SCHEDULED, common_pb2.STARTED, False, False, True, False),
          (common_pb2.STARTED, common_pb2.STARTED, True, False, True, False),
          (common_pb2.SUCCESS, common_pb2.STARTED, True, True, True, False),
          (common_pb2.FAILURE, common_pb2.STARTED, True, True, True, False),
          (
              common_pb2.INFRA_FAILURE, common_pb2.STARTED, False, True, True,
              False
          ),
          (common_pb2.CANCELED, common_pb2.STARTED, False, True, True, False),
          (common_pb2.SUCCESS, common_pb2.FAILURE, True, True, True, True),
          (
              common_pb2.FAILURE, common_pb2.INFRA_FAILURE, True, True, True,
              True
          ),
          (
              common_pb2.FAILURE, common_pb2.INFRA_FAILURE, True, True, False,
              True
          ),
          (
              common_pb2.INFRA_FAILURE, common_pb2.CANCELED, True, True, True,
              True
          ),
          (
              common_pb2.INFRA_FAILURE, common_pb2.CANCELED, False, True, True,
              True
          ),
          (
              common_pb2.INFRA_FAILURE, common_pb2.CANCELED, True, True, False,
              True
          ),
          (
              common_pb2.INFRA_FAILURE, common_pb2.CANCELED, False, True, False,
              True
          ),
      ],
      testcase_func_name=_testcase_func_name,
  )
  def test_parent_child_times_ok(
      self, child, parent, child_started, child_ended, parent_started,
      parent_ended
  ):
    steps = [
        step_pb2.Step(name='a', status=parent),
        step_pb2.Step(name='a|b', status=child)
    ]
    if parent_started:
      steps[0].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
    if parent_ended:
      steps[0].end_time.FromDatetime(datetime.datetime(2019, 2, 1))
    if child_started:
      steps[1].start_time.FromDatetime(datetime.datetime(2018, 2, 1))
    if child_ended:
      steps[1].end_time.FromDatetime(datetime.datetime(2019, 1, 1))

    self.assert_valid(steps)

  def test_duplicate_log_names(self):
    steps = [
        step_pb2.Step(
            name='foo',
            status=common_pb2.SCHEDULED,
            logs=[
                common_pb2.Log(
                    name='tree',
                    url='logdog://0',
                    view_url='logdog.example.com/0'
                ),
                common_pb2.Log(
                    name='branch',
                    url='logdog://1',
                    view_url='logdog.example.com/1'
                ),
                common_pb2.Log(
                    name='tree',
                    url='logdog://2',
                    view_url='logdog.example.com/2'
                )
            ],
        ),
        step_pb2.Step(name='bar', status=common_pb2.SCHEDULED),
    ]
    self.assert_invalid(steps, 'duplicate: u\'tree\'')


class BuildPredicateTests(BaseTestCase):
  func_name = 'validate_build_predicate'

  def test_valid(self):
    msg = rpc_pb2.BuildPredicate(
        builder=build_pb2.BuilderID(
            project='chromium',
            bucket='try',
            builder='linux-rel',
        )
    )
    self.assert_valid(msg)

  def test_empty(self):
    msg = rpc_pb2.BuildPredicate()
    self.assert_valid(msg)

  def test_builder_empty(self):
    msg = rpc_pb2.BuildPredicate(builder=build_pb2.BuilderID())
    self.assert_invalid(msg, r'builder\.project: required')

  def test_builder_project(self):
    msg = rpc_pb2.BuildPredicate(
        builder=build_pb2.BuilderID(project='chromium')
    )
    self.assert_valid(msg)

  def test_builder_project_bucket(self):
    msg = rpc_pb2.BuildPredicate(
        builder=build_pb2.BuilderID(project='chromium', bucket='try')
    )
    self.assert_valid(msg)

  def test_builder_project_builder(self):
    msg = rpc_pb2.BuildPredicate(
        builder=build_pb2.BuilderID(project='chromium', builder='linux-rel')
    )
    self.assert_invalid(msg, 'builder.bucket: required by .builder field')

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


class RequestedDimensionTests(BaseTestCase):
  func_name = 'validate_requested_dimension'

  def test_valid(self):
    msg = common_pb2.RequestedDimension(key='a', value='b')
    self.assert_valid(msg)

  def test_valid_with_expiration(self):
    msg = common_pb2.RequestedDimension(
        key='a', value='b', expiration=dict(seconds=60)
    )
    self.assert_valid(msg)

  def test_valid_with_no_key(self):
    msg = common_pb2.RequestedDimension(key='', value='b')
    self.assert_invalid(msg, r'key: required')

  def test_valid_with_no_value(self):
    msg = common_pb2.RequestedDimension(key='a', value='')
    self.assert_invalid(msg, r'value: required')

  def test_valid_with_caches(self):
    msg = common_pb2.RequestedDimension(key='caches', value='b')
    self.assert_invalid(msg, r'key: "caches" is invalid')

  def test_valid_with_pool(self):
    msg = common_pb2.RequestedDimension(key='pool', value='b')
    self.assert_invalid(msg, r'key: "pool" is not allowed')

  def test_valid_with_negative_seconds(self):
    msg = common_pb2.RequestedDimension(
        key='a', value='b', expiration=dict(seconds=-1)
    )
    self.assert_invalid(msg, r'seconds: must not be negative')

  def test_valid_with_42_seconds(self):
    msg = common_pb2.RequestedDimension(
        key='a', value='b', expiration=dict(seconds=42)
    )
    self.assert_invalid(msg, r'seconds: must be a multiple of 60')

  def test_valid_with_nanos(self):
    msg = common_pb2.RequestedDimension(
        key='a', value='b', expiration=dict(nanos=1)
    )
    self.assert_invalid(msg, r'nanos: must be 0')
