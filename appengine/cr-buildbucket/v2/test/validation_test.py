# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

from google.protobuf import field_mask_pb2

from proto import common_pb2
from proto import build_pb2
from proto import notification_pb2
from proto import rpc_pb2
from proto import step_pb2

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


class ScheduleBuildRequestTests(BaseTestCase):
  func_name = 'validate_schedule_build_request'

  def test_valid(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        request_id='request id',
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        gitiles_commit=common_pb2.GitilesCommit(
            host='gerrit.example.com',
            project='project',
            id='a' * 40,
            ref='refs/heads/master',
            position=1,
        ),
        gerrit_changes=[
            common_pb2.GerritChange(
                host='gerrit.example.com', change=1, patchset=1
            ),
            common_pb2.GerritChange(
                host='gerrit.example.com', change=2, patchset=2
            ),
        ],
        tags=[
            common_pb2.StringPair(key='a', value='a1'),
            common_pb2.StringPair(key='a', value='a2'),
            common_pb2.StringPair(key='b', value='b1'),
        ],
        dimensions=[
            common_pb2.StringPair(key='d1', value='dv1'),
            common_pb2.StringPair(key='d1', value='dv2'),
            common_pb2.StringPair(key='d2', value='dv3'),
            common_pb2.StringPair(key='d3', value=''),
        ],
        priority=100,
        notify=notification_pb2.NotificationConfig(
            pubsub_topic='projects/project_id/topics/topic_id',
            user_data='blob',
        ),
    )
    msg.properties.update({'a': 1, '$recipe_engine/runtime': {'b': 1}})
    self.assert_valid(msg)

  def test_empty(self):
    msg = rpc_pb2.ScheduleBuildRequest()
    self.assert_invalid(msg, 'request_id: required')

  def test_no_builder_and_template_build_id(self):
    msg = rpc_pb2.ScheduleBuildRequest(request_id='request id')
    self.assert_invalid(msg, 'builder or template_build_id is required')

  def test_no_builder_but_template_build_id(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        request_id='request id', template_build_id=1
    )
    self.assert_valid(msg)

  def test_incomplete_builder(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        request_id='request id',
        builder=build_pb2.BuilderID(project='chromium', bucket='try'),
    )
    self.assert_invalid(msg, 'builder.builder: required')

  def test_reserved_properties(self):
    properties = [
        {'buildbucket': 1},
        {'buildername': 1},
        {'blamelist': 1},
        {'$recipe_engine/runtime': {'is_luci': 1}},
        {'$recipe_engine/runtime': {'is_experimental': 1}},
    ]
    for p in properties:
      msg = rpc_pb2.ScheduleBuildRequest(
          request_id='request id',
          builder=build_pb2.BuilderID(
              project='chromium', bucket='try', builder='linux-rel'
          ),
      )
      msg.properties.update(p)
      print msg.properties
      self.assert_invalid(msg, r'property .+ is reserved')

  def test_gitiles_commit_incomplete(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        request_id='request id',
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        gitiles_commit=common_pb2.GitilesCommit(
            host='gerrit.example.com', project='project'
        ),
    )
    self.assert_invalid(msg, r'gitiles_commit: id or ref is required')

  def test_gerrit_change(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        request_id='request id',
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
        request_id='request id',
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        tags=[common_pb2.StringPair()]
    )
    self.assert_invalid(msg, r'tags: Invalid tag ":": starts with ":"')

  def test_dimensions(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        request_id='request id',
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        dimensions=[common_pb2.StringPair()]
    )
    self.assert_invalid(msg, r'dimensions\[0\]\.key: required')

  def test_priority(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        request_id='request id',
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        priority=256,
    )
    self.assert_invalid(msg, r'priority: must be in \[0, 255\]')

  def test_notify_pubsub_topic(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        request_id='request id',
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        notify=notification_pb2.NotificationConfig(),
    )
    self.assert_invalid(msg, r'notify.pubsub_topic: required')

  def test_notify_user_data(self):
    msg = rpc_pb2.ScheduleBuildRequest(
        request_id='request id',
        builder=build_pb2.BuilderID(
            project='chromium', bucket='try', builder='linux-rel'
        ),
        notify=notification_pb2.NotificationConfig(
            pubsub_topic='x',
            user_data='a' * 5000,
        ),
    )
    self.assert_invalid(msg, r'notify.user_data: must be <= 4096 bytes')


class UpdateBuildRequestTests(BaseTestCase):
  func_name = 'validate_update_build_request'

  def test_valid(self):
    msg = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(
            steps=[
                step_pb2.Step(
                    name='foo',
                    status=common_pb2.SUCCESS,
                    logs=[
                        step_pb2.Step.Log(
                            name='tree',
                            url='logdog://0',
                            view_url='logdog.example.com/0'
                        ),
                        step_pb2.Step.Log(
                            name='branch',
                            url='logdog://1',
                            view_url='logdog.example.com/1'
                        )
                    ],
                ),
                step_pb2.Step(
                    name='bar',
                    status=common_pb2.STARTED,
                    logs=[
                        step_pb2.Step.Log(
                            name='tree',
                            url='logdog://2',
                            view_url='logdog.example.com/2'
                        ),
                        step_pb2.Step.Log(
                            name='wood',
                            url='logdog://3',
                            view_url='logdog.example.com/3'
                        )
                    ],
                ),
                step_pb2.Step(
                    name='baz',
                    status=common_pb2.SCHEDULED,
                ),
            ]
        ),
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )
    msg.build.steps[0].start_time.FromDatetime(datetime.datetime(2017, 1, 1))
    msg.build.steps[0].end_time.FromDatetime(datetime.datetime(2018, 1, 1))
    msg.build.steps[1].start_time.FromDatetime(datetime.datetime(2017, 2, 1))
    self.assert_valid(msg)

  def test_missing_build(self):
    msg = rpc_pb2.UpdateBuildRequest(
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )
    self.assert_invalid(msg, 'required')

  def test_missing_update_mask(self):
    msg = rpc_pb2.UpdateBuildRequest(build=build_pb2.Build())
    self.assert_invalid(msg, 'update only supports build.steps path currently')

  def test_duplicate_step_names(self):
    msg = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(
            steps=[
                step_pb2.Step(name='foo', status=common_pb2.SCHEDULED),
                step_pb2.Step(name='bar', status=common_pb2.SCHEDULED),
                step_pb2.Step(name='foo', status=common_pb2.SCHEDULED),
            ]
        ),
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )
    self.assert_invalid(msg, 'duplicate: u\'foo\'')

  def test_bad_step_status(self):
    msg_unspecified = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(
            steps=[
                step_pb2.Step(name='foo', status=common_pb2.SCHEDULED),
                step_pb2.Step(name='bar'),
            ]
        ),
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )

    msg_invalid = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(steps=[
            step_pb2.Step(name='foo', status=3),
        ]),
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )

    for msg in [msg_unspecified, msg_invalid]:
      self.assert_invalid(
          msg, 'must have buildbucket.v2.Status that is not STATUS_UNSPECIFIED'
      )

  def test_inconsistent_end_time_terminal_status(self):
    msg_status = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(
            steps=[
                step_pb2.Step(name='foo', status=common_pb2.STARTED),
            ]
        ),
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )
    msg_status.build.steps[0].start_time.FromDatetime(
        datetime.datetime(2018, 1, 1)
    )
    msg_status.build.steps[0].end_time.FromDatetime(
        datetime.datetime(2019, 1, 1)
    )

    msg_time = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(
            steps=[
                step_pb2.Step(name='foo', status=common_pb2.SUCCESS),
            ]
        ),
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )
    msg_time.build.steps[0].start_time.FromDatetime(
        datetime.datetime(2018, 1, 1)
    )

    for msg in [msg_status, msg_time]:
      self.assert_invalid(
          msg, 'must have both or neither end_time and a terminal status'
      )

  def test_inconsistent_start_time_started_status(self):
    msg_status = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(
            steps=[
                step_pb2.Step(name='foo', status=common_pb2.SCHEDULED),
            ]
        ),
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )
    msg_status.build.steps[0].start_time.FromDatetime(
        datetime.datetime(2018, 1, 1)
    )

    msg_time = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(
            steps=[
                step_pb2.Step(name='foo', status=common_pb2.STARTED),
            ]
        ),
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )

    for msg in [msg_status, msg_time]:
      self.assert_invalid(
          msg,
          'must have both or neither start_time and an at least started status'
      )

  def test_bad_step_start_end_times(self):
    msg = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(
            steps=[
                step_pb2.Step(name='foo', status=common_pb2.SUCCESS),
                step_pb2.Step(name='bar', status=common_pb2.SCHEDULED),
            ]
        ),
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )
    msg.build.steps[0].start_time.FromDatetime(datetime.datetime(2018, 1, 1))
    msg.build.steps[0].end_time.FromDatetime(datetime.datetime(2017, 1, 1))
    self.assert_invalid(msg, 'start_time after end_time')

  def test_duplicate_log_names(self):
    msg = rpc_pb2.UpdateBuildRequest(
        build=build_pb2.Build(
            steps=[
                step_pb2.Step(
                    name='foo',
                    status=common_pb2.SCHEDULED,
                    logs=[
                        step_pb2.Step.Log(
                            name='tree',
                            url='logdog://0',
                            view_url='logdog.example.com/0'
                        ),
                        step_pb2.Step.Log(
                            name='branch',
                            url='logdog://1',
                            view_url='logdog.example.com/1'
                        ),
                        step_pb2.Step.Log(
                            name='tree',
                            url='logdog://2',
                            view_url='logdog.example.com/2'
                        )
                    ],
                ),
                step_pb2.Step(
                    name='bar',
                    status=common_pb2.SCHEDULED,
                ),
            ]
        ),
        update_mask=field_mask_pb2.FieldMask(paths=['build.steps']),
    )
    self.assert_invalid(msg, 'duplicate: u\'tree\'')


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
