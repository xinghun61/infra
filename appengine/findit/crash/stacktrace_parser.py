# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class StacktraceParser(object):

  def Parse(self, stacktrace_string, deps):
    raise NotImplementedError()

  def _IsStartOfNewCallStack(self, line):
    raise NotImplementedError()
