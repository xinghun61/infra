#!/bin/bash
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
python2.5 ../google_appengine/dev_appserver.py . --require_indexes \
   --debug -a 0.0.0.0 --disable_static_caching $@
