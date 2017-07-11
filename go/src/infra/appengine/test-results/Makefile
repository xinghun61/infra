# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Makefile to simplify some common actions.
# Use 'make help' for a list of commands.

.PHONY: help build clean test devserver deploy_staging_run deploy_staging	\
	deploy_prod_run deploy_prod deploy_cron_prod deploy_dispatch_prod				\
	deploy_queues_prod deploy_cron_staging deploy_dispatch_staging					\
	deploy_queues_staging

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

build:
	cd frontend && bower install
	cd frontend && vulcanize src/test-results.html --out-html src/test-results.vulcanized.html

clean:
	cd frontend && rm -f src/test-results.vulcanized.html

test:
	go test -race ./...

devserver:
	dev_appserver.py frontend/app.yaml

# We can not use gae.py below because test-results is a mixed Python/Go app and
# gae.py does not support that.

dirty=
ifneq ($(shell git status --porcelain --untracked-files=no),)
  dirty="-tainted"
endif
VERSION?= `git show --format='%h' --no-patch`$(dirty)

deploy_staging_run:
	appcfg.py -A test-results-test-hrd -V ${VERSION} update frontend/app.yaml
	@echo
	@echo "Deployed version is at https://${VERSION}-dot-test-results-test.appspot.com/"
	@echo "Version management console is at https://pantheon.corp.google.com/appengine/versions?project=test-results-test-hrd"
	@echo

deploy_staging: build deploy_staging_run clean

deploy_prod_run:
	appcfg.py -A test-results-hrd -V ${VERSION} update frontend/app.yaml
	@echo
	@echo "Deployed version is at https://${VERSION}-dot-test-results.appspot.com/"
	@echo "Version management console is at https://pantheon.corp.google.com/appengine/versions?project=test-results-hrd"
	@echo

deploy_prod: build deploy_prod_run clean

deploy_cron_prod:
	appcfg.py -A test-results-hrd -V ${VERSION} update_cron .

deploy_dispatch_prod:
	appcfg.py -A test-results-hrd -V ${VERSION} update_dispatch .

deploy_queues_prod:
	appcfg.py -A test-results-hrd -V ${VERSION} update_queues .

deploy_cron_staging:
	appcfg.py -A test-results-test-hrd -V ${VERSION} update_cron .

deploy_dispatch_staging:
	appcfg.py -A test-results-test-hrd -V ${VERSION} update_dispatch .

deploy_queues_staging:
	appcfg.py -A test-results-test-hrd -V ${VERSION} update_queues .
