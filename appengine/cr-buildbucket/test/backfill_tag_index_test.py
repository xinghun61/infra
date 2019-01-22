# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from test import test_util
from test.test_util import future_exception
from testing_utils import testing
import backfill_tag_index
import search


class BackfillTagIndexTest(testing.AppengineTestCase):

  def setUp(self):
    super(BackfillTagIndexTest, self).setUp()
    self.patch('search.TagIndex.random_shard_index', return_value=0)
    self.patch('backfill_tag_index._enqueue_flush_entries')

  def test_process(self):
    builds = [
        test_util.build(
            id=i,
            tags=[
                dict(key='t', value='%d' % (i % 3)),
                dict(key='a', value='b'),
            ],
        ) for i in xrange(50, 60)
    ]

    backfill_tag_index._process_builds(builds, 't', 5)

    backfill_tag_index._enqueue_flush_entries.assert_called_with(
        't', {
            '0': [
                ['chromium/try', 51],
                ['chromium/try', 54],
            ],
            '1': [['chromium/try', 52]],
            '2': [
                ['chromium/try', 50],
                ['chromium/try', 53],
            ],
        }
    )

  def test_flush_entries(self):
    search.TagIndex(
        id='buildset:0',
        entries=[
            search.TagIndexEntry(bucket_id='chromium/try', build_id=51),
        ]
    ).put()
    search.TagIndex(
        id='buildset:2',
        entries=[
            search.TagIndexEntry(bucket_id='chromium/try', build_id=1),
            search.TagIndexEntry(bucket_id='chromium/try', build_id=100),
        ]
    ).put()

    backfill_tag_index._flush_entries(
        'buildset',
        {
            '0': [['chromium/try', 51]],
            '1': [['chromium/try', 52]],
            '2': [['chromium/try', 50]],
        },
    )

    idx0 = search.TagIndex.get_by_id('buildset:0')
    self.assertIsNotNone(idx0)
    self.assertEqual(len(idx0.entries), 1)
    self.assertEqual(idx0.entries[0].build_id, 51)

    idx1 = search.TagIndex.get_by_id('buildset:1')
    self.assertIsNotNone(idx1)
    self.assertEqual(len(idx1.entries), 1)
    self.assertEqual(idx1.entries[0].build_id, 52)

    idx2 = search.TagIndex.get_by_id('buildset:2')
    self.assertIsNotNone(idx2)
    self.assertEqual(len(idx2.entries), 3)
    self.assertEqual({e.build_id for e in idx2.entries}, {1, 50, 100})

  def test_flush_entries_retry(self):
    orig_add_async = backfill_tag_index._add_index_entries_async

    def add_async(tag, entries):
      if tag == 'buildset:1':
        return future_exception(Exception('transient error'))
      return orig_add_async(tag, entries)

    with mock.patch(
        'backfill_tag_index._add_index_entries_async',
        side_effect=add_async,
    ):
      backfill_tag_index._flush_entries(
          'buildset',
          {
              '0': [['chromium/try', 51]],
              '1': [['chromium/try', 52]],
              '2': [['chromium/try', 50]],
          },
      )

    idx0 = search.TagIndex.get_by_id('buildset:0')
    self.assertIsNotNone(idx0)
    self.assertEqual(len(idx0.entries), 1)
    self.assertEqual(idx0.entries[0].build_id, 51)

    idx2 = search.TagIndex.get_by_id('buildset:2')
    self.assertIsNotNone(idx2)
    self.assertEqual(len(idx2.entries), 1)
    self.assertEqual(idx2.entries[0].build_id, 50)

    backfill_tag_index._enqueue_flush_entries.assert_called_with(
        'buildset', {'1': [['chromium/try', 52]]}
    )

  def test_flush_entries_too_many(self):
    backfill_tag_index._flush_entries(
        'buildset',
        {'0': [['chromium/try', i] for i in xrange(1, 2001)]},
    )

    idx0 = search.TagIndex.get_by_id('buildset:0')
    self.assertIsNotNone(idx0)
    self.assertTrue(idx0.permanently_incomplete)
    self.assertEqual(len(idx0.entries), 0)

    # once more for coverage
    backfill_tag_index._flush_entries(
        'buildset',
        {'0': [['chromium/try', 1]]},
    )
