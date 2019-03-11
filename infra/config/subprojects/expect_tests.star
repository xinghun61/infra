# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of expect_tests.git CI resources."""

load('//lib/presubmit.star', 'presubmit')


REPO_URL = 'https://chromium.googlesource.com/infra/testing/expect_tests'

luci.cq_group(
    name = 'expect_tests cq',
    watch = cq.refset(repo = REPO_URL, refs = [r'refs/heads/.+']),
    retry_config = cq.RETRY_NONE,
)


presubmit.builder(
    name = 'Expect-Tests Presubmit',
    cq_group = 'expect_tests cq',
    repo_name = 'expect_tests',
)
