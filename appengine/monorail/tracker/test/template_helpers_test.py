# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for the template helpers module."""

import unittest

import settings

from testing import fake
from tracker import template_helpers
from tracker import tracker_bizobj
from proto import tracker_pb2


class TemplateHelpers(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

  def testParseTemplateRequest_Empty(self):
    post_data = fake.PostData()
    parsed = template_helpers.ParseTemplateRequest(post_data, self.config)
    self.assertEqual(parsed.name, '')
    self.assertEqual(parsed.members_only, False)
    self.assertEqual(parsed.summary, '')
    self.assertEqual(parsed.summary_must_be_edited, False)
    self.assertEqual(parsed.content, '')
    self.assertEqual(parsed.status, '')
    self.assertEqual(parsed.owner_str, '')
    self.assertEqual(parsed.labels, [])
    self.assertEqual(parsed.field_val_strs, {})
    self.assertEqual(parsed.component_paths, [])
    self.assertEqual(parsed.component_required, False)
    self.assertEqual(parsed.owner_defaults_to_member, False)

  def testParseTemplateRequest_Normal(self):
    fd_1 = tracker_bizobj.MakeFieldDef(
        1, 789, 'UXReview', tracker_pb2.FieldTypes.STR_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'Approval for UX review', False)
    fd_2 = tracker_bizobj.MakeFieldDef(
        2, 789, 'InternalScream', tracker_pb2.FieldTypes.STR_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'Approval for UX review', False)
    self.config.field_defs.append(fd_1)
    self.config.field_defs.append(fd_2)
    post_data = fake.PostData(
        name=['sometemplate'],
        members_only=['yes'],
        summary=['TLDR'],
        summary_must_be_edited=['yes'],
        content=['HEY WHY'],
        status=['Accepted'],
        owner=['someone@world.com'],
        label=['label-One', 'label-Two'],
        field_value_1=['NO'],
        field_value_2=['MOOD'],
        components=['hey, hey2,he3'],
        component_required=['yes'],
        owner_defaults_to_memeber=['no']
    )

    parsed = template_helpers.ParseTemplateRequest(post_data, self.config)
    self.assertEqual(parsed.name, 'sometemplate')
    self.assertEqual(parsed.members_only, True)
    self.assertEqual(parsed.summary, 'TLDR')
    self.assertEqual(parsed.summary_must_be_edited, True)
    self.assertEqual(parsed.content, 'HEY WHY')
    self.assertEqual(parsed.status, 'Accepted')
    self.assertEqual(parsed.owner_str, 'someone@world.com')
    self.assertEqual(parsed.labels, ['label-One', 'label-Two'])
    self.assertEqual(parsed.field_val_strs, {1: ['NO'], 2: ['MOOD']})
    self.assertEqual(parsed.component_paths, ['hey', 'hey2', 'he3'])
    self.assertEqual(parsed.component_required, True)
    self.assertEqual(parsed.owner_defaults_to_member, False)
