# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

test:
	./node_modules/karma/bin/karma start

single-test:
	./node_modules/karma/bin/karma start --single-run

vulcanize:
	mkdir -p ./gen
	./node_modules/vulcanize/bin/vulcanize sheriff-o-matic.html -o gen/index.html

deploy-staging: vulcanize
	../../../google_appengine/appcfg.py update_dispatch -A sheriff-o-matic-staging .
	../../../google_appengine/appcfg.py update -A sheriff-o-matic-staging . --version `git rev-parse --short HEAD`

deploy-staging-monitoring:
	../../../google_appengine/appcfg.py update -A sheriff-o-matic-staging appengine_module/gae_ts_mon/monitoring.yaml --version `git rev-parse --short HEAD`

deploy-prod: vulcanize
	../../../google_appengine/appcfg.py update . --version `git rev-parse --short HEAD`
	../../../google_appengine/appcfg.py update_dispatch -A sheriff-o-matic .
	../../../google_appengine/appcfg.py update -A sheriff-o-matic appengine_module/gae_ts_mon/monitoring.yaml --version `git rev-parse --short HEAD`

.PHONY: test single-test
