# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by the Apache v2.0 license that can be
# found in the LICENSE file.

build:
	cd proto && $(MAKE)

test: build
	tools/run_tests.sh

deploy: build
	tools/gae upload -x

upload: build
	tools/gae upload

rollback:
	appcfg.py -V `tools/gae version` rollback .
