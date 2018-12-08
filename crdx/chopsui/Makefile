# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

node_deps:
	npm install

bower_deps: node_deps
	npx bower install

wct: bower_deps
	npx run-wct --prefix test --dep bower_components

wct_debug: bower_deps
	npx run-wct --prefix test --dep bower_components --debug
