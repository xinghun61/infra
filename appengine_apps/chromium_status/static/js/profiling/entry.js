// Copyright (c) 2011 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Represents a record in the profiling database.
 * @constructor
 */
function Entry(
    timestamp, domain, platform, duration, argv, executable, first_arg) {
  this.timestamp = timestamp;
  this.domain = domain;
  this.platform = platform;
  this.duration = duration;
  this.argv = argv;
  this.executable = executable;
  this.first_arg = first_arg;
}
