# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs import dashboard_util
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from handlers.disabled_tests.detection import disabled_test_detection_utils
from model.test_inventory import LuciTest

_DEFAULT_LUCI_PROJECT = 'chromium'


def _GetDisabledTestsQueryResults(cursor, direction, page_size):
  """Gets queried results of disabled tests.

  Args:
    cursor (None or str): The cursor provides a cursor in the current query
      results, allowing you to retrieve the next set based on the offset.
    direction (str): Either previous or next.
    page_size (int): Number of entities to show per page.

  Returns:
    A tuple of (disabled_tests, prev_cursor, cursor).
    disabled_tests ([LuciTest]): List of disabled_tests to be displayed at the
      current page.
    prev_cursor (str): The urlsafe encoding of the cursor, which is at the
      top position of entities of the current page.
    cursor (str): The urlsafe encoding of the cursor, which is at the
      bottom position of entities of the current page.
  """

  disabled_tests_query = LuciTest.query(LuciTest.disabled == True)  # pylint: disable=singleton-comparison

  return dashboard_util.GetPagedResults(
      disabled_tests_query,
      order_properties=[
          (LuciTest.last_updated_time, dashboard_util.DESC),
          (LuciTest.normalized_test_name, dashboard_util.ASC),
      ],
      cursor=cursor,
      direction=direction,
      page_size=page_size)


class DisplayTestDisablement(BaseHandler):
  """Queries disabled tests and ranks them by update time in descending order.
  """
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    page_size = int(self.request.get('page_size').strip()) if self.request.get(
        'page_size') else disabled_test_detection_utils.DEFAULT_PAGE_SIZE
    prev_cursor = ''
    cursor = ''
    error_message = None

    disabled_tests, prev_cursor, cursor = _GetDisabledTestsQueryResults(
        self.request.get('cursor'),
        self.request.get('direction').strip(), page_size)

    tests_data = disabled_test_detection_utils.GenerateDisabledTestsData(
        disabled_tests)

    data = {
        'disabled_tests_data':
            tests_data,
        'prev_cursor':
            prev_cursor,
        'cursor':
            cursor,
        'page_size': (
            page_size if
            page_size != disabled_test_detection_utils.DEFAULT_PAGE_SIZE else ''
        ),
        'error_message':
            error_message,
    }
    return {
        'template': 'disabled_test/detection/display_test_disablement.html',
        'data': data
    }
