# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Label for Chromium Sheriff bug queue.
SHERIFF_CHROMIUM_LABEL = 'Sheriff-Chromium'

# Label for Type-Bug.
TYPE_BUG_LABEL = 'Type-Bug'

# Label used to identify issues related to flaky tests.
FLAKY_TEST_LABEL = 'Test-Flaky'

# Label used to identify issues filed against Findit due to wrong results.
TEST_FINDIT_WRONG_LABEL = 'Test-Findit-Wrong'

# Component used to identify issues related to flaky tests.
FLAKY_TEST_COMPONENT = 'Tests>Flaky'

# Customized field for flaky test.
FLAKY_TEST_CUSTOMIZED_FIELD = 'Flaky-Test'

FINDIT_ANALYZED_LABEL_TEXT = 'Test-Findit-Analyzed'

FLAKE_DETECTION_LABEL_TEXT = 'Test-Findit-Detected'

# Query used to search for flaky test in customized field.
FLAKY_TEST_CUSTOMIZED_FIELD_QUERY_TEMPLATE = (
    '%s={} is:open' % FLAKY_TEST_CUSTOMIZED_FIELD)

# A list of keywords in issue summary to identify issues that are related to
# flaky tests.
FLAKY_TEST_SUMMARY_KEYWORDS = ['flake', 'flaky', 'flakiness']

# Query used to search for flaky test in summary.
FLAKY_TEST_SUMMARY_QUERY_TEMPLATE = 'summary:{} is:open'

# Customized field for flaky test.
FLAKY_TEST_GROUP_CUSTOMIZED_FIELD = 'Flaky-Test-Suite'

# Query used to search for flaky test suite in customized field.
FLAKY_TEST_GROUP_CUSTOMIZED_FIELD_QUERY_TEMPLATE = (
    '%s={} is:open' % FLAKY_TEST_GROUP_CUSTOMIZED_FIELD)
