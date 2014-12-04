# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

NPM_VERSION := $(shell npm --version 2>/dev/null)
BOWER_VERSION := $(shell bower --version 2>/dev/null)

check:
ifndef NPM_VERSION
	$(error npm not found. Please install it)
endif
ifndef BOWER_VERSION
	@echo "bower not found. It can be installed with 'npm install [-g] bower'";
endif

test: check
	../third_party/npm_modules/node_modules/karma/bin/karma start

single-test: check
	../third_party/npm_modules/node_modules/karma/bin/karma start --single-run

.PHONY: check update test single-test
