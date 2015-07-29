# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

vulcanize: check
	mkdir -p ./gen
	../third_party/npm_modules/node_modules/vulcanize/bin/vulcanize --abspath html html/main.html -o vulcanized_main.html

deploy: vulcanize
	appcfg.py --oauth2 update . --version `git rev-parse --short HEAD`

.PHONY: check test single-test
