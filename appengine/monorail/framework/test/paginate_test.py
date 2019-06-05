# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for pagination classes."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import paginate
from testing import testing_helpers


class PaginateTest(unittest.TestCase):

  def testVirtualPagination(self):
    # Paginating 0 results on a page that can hold 100.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list')
    total_count = 0
    items_per_page = 100
    start = 0
    vp = paginate.VirtualPagination(total_count, items_per_page, start)
    self.assertEquals(vp.num, 100)
    self.assertEquals(vp.start, 1)
    self.assertEquals(vp.last, 0)
    self.assertFalse(vp.visible)

    # Paginating 12 results on a page that can hold 100.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list')
    vp = paginate.VirtualPagination(12, 100, 0)
    self.assertEquals(vp.num, 100)
    self.assertEquals(vp.start, 1)
    self.assertEquals(vp.last, 12)
    self.assertTrue(vp.visible)

    # Paginating 12 results on a page that can hold 10.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list?num=10')
    vp = paginate.VirtualPagination(12, 10, 0)
    self.assertEquals(vp.num, 10)
    self.assertEquals(vp.start, 1)
    self.assertEquals(vp.last, 10)
    self.assertTrue(vp.visible)

    # Paginating 12 results starting at 5 on page that can hold 10.
    mr = testing_helpers.MakeMonorailRequest(
        path='/issues/list?start=5&num=10')
    vp = paginate.VirtualPagination(12, 10, 5)
    self.assertEquals(vp.num, 10)
    self.assertEquals(vp.start, 6)
    self.assertEquals(vp.last, 12)
    self.assertTrue(vp.visible)

    # Paginating 123 results on a page that can hold 100.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list')
    vp = paginate.VirtualPagination(123, 100, 0)
    self.assertEquals(vp.num, 100)
    self.assertEquals(vp.start, 1)
    self.assertEquals(vp.last, 100)
    self.assertTrue(vp.visible)

    # Paginating 123 results on second page that can hold 100.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list?start=100')
    vp = paginate.VirtualPagination(123, 100, 100)
    self.assertEquals(vp.num, 100)
    self.assertEquals(vp.start, 101)
    self.assertEquals(vp.last, 123)
    self.assertTrue(vp.visible)

    # Paginating a huge number of objects will show at most 1000 per page.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list?num=9999')
    vp = paginate.VirtualPagination(12345, 9999, 0)
    self.assertEquals(vp.num, 1000)
    self.assertEquals(vp.start, 1)
    self.assertEquals(vp.last, 1000)
    self.assertTrue(vp.visible)

    # Test urls for a hotlist pagination
    mr = testing_helpers.MakeMonorailRequest(path='/hotlists/17?num=5&start=4')
    mr.hotlist_id = 17
    mr.auth.user_id = 112
    vp = paginate.VirtualPagination(12, 5, 4,
                                    list_page_url='/u/112/hotlists/17')
    self.assertEquals(vp.num, 5)
    self.assertEquals(vp.start, 5)
    self.assertEquals(vp.last, 9)
    self.assertTrue(vp.visible)
    self.assertEqual('/u/112/hotlists/17?num=5&start=9', vp.next_url)
    self.assertEqual('/u/112/hotlists/17?num=5&start=0', vp.prev_url)
