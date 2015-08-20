# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Metrics common to all tasks and devices."""

from infra_libs.ts_mon import metrics

# TODO(dsansome): Add more metrics for git revision, cipd package version,
# uptime, etc.
up = metrics.BooleanMetric('presence/up')


def init():
  up.set(True)
