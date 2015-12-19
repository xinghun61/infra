# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for the tree listing API."""

import datetime
import json

from components import utils
from components import auth
from google.appengine.ext import ndb
import mock

from testing_utils import testing
import tree

class TreeAuthApiTest(testing.AppengineTestCase):
  @property
  def app_module(self):
    return tree.list_app

  def setUp(self):
    super(TreeAuthApiTest, self).setUp()

    self.external_tree = tree.Tree(
      id="chromium",
      display_name="Chromium",
    )
    self.internal_tree = tree.Tree(
      id="internal_tree",
      display_name="Internal tree breh",
      group="googlers",
    )

    self.is_internal = False
    def igm(grp):
      if grp == '*':
        return True
      return self.is_internal
    self.mock(auth, 'is_group_member', igm)

  def test_external_user(self):
    self.external_tree.put()
    self.internal_tree.put()

    res = self.test_app.get('/tree-list')
    tree_names = [t['name'] for t in res.json_body['trees']]
    self.assertIn('chromium', tree_names)
    self.assertNotIn('internal_tree', tree_names)

  def test_internal_user(self):
    self.external_tree.put()
    self.internal_tree.put()
    self.is_internal = True

    res = self.test_app.get('/tree-list')
    tree_names = [t['name'] for t in res.json_body['trees']]
    self.assertIn('chromium', tree_names)
    self.assertIn('internal_tree', tree_names)


class TreeEndpointsTest(testing.EndpointsTestCase):
  api_service_cls = tree.TreeEndpointsApi

  def setUp(self):
    super(TreeEndpointsTest, self).setUp()

    self.tree = tree.Tree(
      id="chromium",
      display_name="Chromium",
    )

    self.is_admin = True
    self.mock(auth, 'is_admin', lambda: self.is_admin)

  def test_put_no_admin(self):
    self.is_admin = False
    with self.call_should_fail(404):
      self.call_api('new', {})

  def test_put_duplicate(self):
    self.tree.put()
    with self.call_should_fail(403):
      self.call_api('new', {
          'name': self.tree.key.string_id(),
      })

  def test_put(self):
    req = {
      'name': "chromium",
      'display_name': 'Chromium',
      'group': 'abc',
    }

    self.call_api('new', req)

    got_tree = tree.Tree.get_by_id('chromium')
    self.assertEqual(got_tree.display_name, "Chromium")
    self.assertEqual(got_tree.group, "abc")

  def test_bug_label_no_admin(self):
    self.is_admin = False
    with self.call_should_fail(404):
      self.call_api('add_bug_label', {
          'tree': 'test',
          'label': 'blahbllah',
      })

  def test_bug_label_no_tree(self):
    with self.call_should_fail(404):
      self.call_api('add_bug_label', {
          'tree': 'test',
          'label': 'blahbllah',
      })

  def test_bug_label(self):
    self.tree.put()

    got_tree = tree.Tree.get_by_id('chromium')
    self.assertEqual(got_tree.bug_labels, [])

    self.call_api('add_bug_label', {
        'tree': 'chromium',
        'label': 'foobar',
    })

    got_tree = tree.Tree.get_by_id('chromium')
    self.assertEqual(got_tree.bug_labels, ['foobar'])

  def test_bug_label_no_duplicates(self):
    self.tree.bug_labels.append('fishies!!')
    self.tree.put()

    got_tree = tree.Tree.get_by_id('chromium')
    self.assertEqual(got_tree.bug_labels, ['fishies!!'])

    self.call_api('add_bug_label', {
        'tree': 'chromium',
        'label': 'fishies!!',
    })

    got_tree = tree.Tree.get_by_id('chromium')
    self.assertEqual(got_tree.bug_labels, ['fishies!!'])
