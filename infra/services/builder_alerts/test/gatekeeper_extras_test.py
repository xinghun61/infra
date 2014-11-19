# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from infra.services.builder_alerts import gatekeeper_extras


class GatekeeperExtrasTest(unittest.TestCase):
  def test_excluded_builders(self):
    self.assertEqual(gatekeeper_extras.excluded_builders([{}]), set())
    self.assertEqual(gatekeeper_extras.excluded_builders([{'*': {}}]), set())
    self.assertEqual(
        gatekeeper_extras.excluded_builders(
            [{'*': {
                'excluded_builders': set(['test_builder1', 'test_builder2'])
            }}]),
        set(['test_builder1', 'test_builder2']))

  @mock.patch(
      'infra.services.builder_alerts.gatekeeper_extras.excluded_builders',
      lambda config: ['Ignored'])
  @mock.patch(
      'infra.services.builder_alerts.gatekeeper_extras.would_close_tree',
      lambda config, builder, step: True)
  @mock.patch(
      'infra.services.builder_alerts.gatekeeper_extras.tree_for_master',
      lambda master_url, trees_config: 'test-tree')
  def test_apply_gatekeeper_rules(self):
    gatekeeper_cfg = {'http://build.chromium.org/p/chromium': {'key': 'value'}}
    gatekeeper_trees_cfg = {}
    alerts = [
        {'master_url': 'http://build.chromium.org/p/project.without.config',
         'builder_name': 'Linux',
         'step_name': 'test_xyz'},
        {'master_url': 'http://build.chromium.org/p/chromium',
         'builder_name': 'Ignored',
         'step_name': 'bot_update'},
        {'master_url': 'http://build.chromium.org/p/chromium',
         'builder_name': 'Win',
         'step_name': 'bot_update'},
        {'master_url': 'http://build.chromium.org/p/chromium',
         'builder_name': 'Mac'},
        # stale master alert
        {
          'last_update_time': 1234,
          'master_url': 'http://build.chromium.org/p/chromium',
          'master_name': 'chromium',
        },
        # stale builder alert
        {
          'master_url': 'http://build.chromium.org/p/chromium',
          'builder_name': 'Linux',
          'state': 'offline',
          'last_update_time': 1234,
          'pending_builds': [],
          'step': 'bot_update',
          'latest_build': 1234,
        }
    ]

    filtered_alerts = gatekeeper_extras.apply_gatekeeper_rules(
        alerts, gatekeeper_cfg, gatekeeper_trees_cfg)

    self.assertEqual(len(filtered_alerts), 5)
    self.assertIn({'master_url': 'http://build.chromium.org/p/chromium',
                   'builder_name': 'Win',
                   'step_name': 'bot_update',
                   'would_close_tree': True,
                   'tree': 'test-tree'}, filtered_alerts)
    self.assertIn(
        {'master_url': 'http://build.chromium.org/p/project.without.config',
         'builder_name': 'Linux',
         'step_name': 'test_xyz'},
        filtered_alerts)
    self.assertIn(
        {'master_url': 'http://build.chromium.org/p/chromium',
         'builder_name': 'Mac',
         'tree': 'test-tree'},
        filtered_alerts)
    self.assertIn(
        {
          'last_update_time': 1234,
          'master_url': 'http://build.chromium.org/p/chromium',
          'master_name': 'chromium',
          'tree': 'test-tree',
        },
        filtered_alerts)
    self.assertIn(
        {
          'master_url': 'http://build.chromium.org/p/chromium',
          'builder_name': 'Linux',
          'state': 'offline',
          'last_update_time': 1234,
          'pending_builds': [],
          'step': 'bot_update',
          'latest_build': 1234,
          'tree': 'test-tree',
        },
        filtered_alerts)

  def test_tree_for_master_returns_tree_name(self):
    gatekeeper_trees = {
        'blink': {'masters': [
            'https://build.chromium.org/p/chromium.webkit'
        ]},
        'chromium': {'masters': [
            'https://build.chromium.org/p/chromium.linux',
            'https://build.chromium.org/p/chromium.gpu',
        ]},
        'non-closers': {'masters': [
            'https://build.chromium.org/p/chromium.lkgr',
        ]}
    }

    self.assertEqual('chromium', gatekeeper_extras.tree_for_master(
        'https://build.chromium.org/p/chromium.gpu', gatekeeper_trees))
    self.assertEqual('blink', gatekeeper_extras.tree_for_master(
        'https://build.chromium.org/p/chromium.webkit', gatekeeper_trees))
    self.assertEqual('non-closers', gatekeeper_extras.tree_for_master(
        'https://build.chromium.org/p/chromium.lkgr', gatekeeper_trees))

  @mock.patch( # pragma: no cover (decorators are run before coverage is loaded)
      'infra.services.builder_alerts.buildbot.master_name_from_url',
      lambda url: 'foo.bar')
  def test_tree_for_master_falls_back_to_master_name(self):
    self.assertEqual('foo.bar', gatekeeper_extras.tree_for_master(
        'https://build.chromium.org/p/foo.bar', {}))

  def test_fetch_master_urls(self):
    class MockArgs(object):
      def __init__(self, master_filter):
        self.master_filter = master_filter

    gatekeeper = {'test_master1': {}, 'test_master2': {}, 'filtered_master': {}}
    self.assertEqual(
        set(gatekeeper_extras.fetch_master_urls(gatekeeper,
                                                MockArgs('filtered'))),
        set(['test_master1', 'test_master2']))
    self.assertEqual(
        set(gatekeeper_extras.fetch_master_urls(gatekeeper, MockArgs(None))),
        set(['test_master1', 'test_master2', 'filtered_master']))

  def test_would_close_tree_uses_asterisk_builder_config(self):
    self.assertFalse(gatekeeper_extras.would_close_tree(
        [{'*': {'close_tree': False}}], None, 'test_step'))
    self.assertTrue(gatekeeper_extras.would_close_tree(
        [{'*': {'closing_steps': set(['*'])}}], None, 'test_step'))

  def test_would_close_tree_respects_close_tree_flag_field(self):
    self.assertFalse(gatekeeper_extras.would_close_tree(
        [{'test_builder': {'close_tree': False}}], 'test_builder', 'test_step'))

  def test_would_close_tree_respects_excluded_steps_field(self):
    self.assertFalse(gatekeeper_extras.would_close_tree(
        [{'test_builder': {'excluded_steps': ['test_step']}}],
        'test_builder', 'test_step'))

  def test_would_close_tree_only_considers_closing_steps(self):
    self.assertFalse(gatekeeper_extras.would_close_tree(
        [{'test_builder': {'closing_steps': set(['other_step'])}}],
        'test_builder', 'test_step'))

  def test_would_close_tree_assumes_no_closing_steps_when_missing_field(self):
    self.assertFalse(gatekeeper_extras.would_close_tree(
        [{'test_builder': {}}], 'test_builder', 'test_step'))

  def test_would_close_tree_returns_true_if_step_is_in_closing_steps(self):
    self.assertTrue(gatekeeper_extras.would_close_tree(
        [{'test_builder': {'closing_steps': set(['test_step'])}}],
        'test_builder', 'test_step'))

  def test_would_close_tree_returns_true_if_all_steps_are_closing(self):
    self.assertTrue(gatekeeper_extras.would_close_tree(
        [{'test_builder': {'closing_steps': set(['*'])}}],
        'test_builder', 'test_step'))


if __name__ == '__main__':
  unittest.main()