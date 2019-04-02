# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of expect_tests.git CI resources."""

load('//lib/build.star', 'build')


REPO_URL = 'https://chromium.googlesource.com/infra/testing/expect_tests'

luci.cq_group(
    name = 'expect_tests cq',
    watch = cq.refset(repo = REPO_URL, refs = [r'refs/heads/master']),
    retry_config = cq.RETRY_NONE,
)


build.presubmit(
    name = 'Expect-Tests Presubmit',
    cq_group = 'expect_tests cq',
    repo_name = 'expect_tests',
    run_hooks = False,
)
