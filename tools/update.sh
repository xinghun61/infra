#!/bin/bash
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
cd $(dirname $0)
../../google_appengine/appcfg.py update .. -A chromeos-status $@
../../google_appengine/appcfg.py update .. -A chromium-status $@
../../google_appengine/appcfg.py update .. -A chromiumos-status $@
../../google_appengine/appcfg.py update .. -A chromiumos-browser-status $@
../../google_appengine/appcfg.py update .. -A gyp-status $@
../../google_appengine/appcfg.py update .. -A naclports-status $@
../../google_appengine/appcfg.py update .. -A naclsdk-status $@
../../google_appengine/appcfg.py update .. -A nativeclient-status $@
../../google_appengine/appcfg.py update .. -A o3d-status $@
