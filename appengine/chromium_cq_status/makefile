# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Allow overwriting application id, so one can deploy them with:
# $ APP_ID='whatever' make deploy
APP_ID ?= chromium-cq-status
NPM_VERSION := $(shell npm --version 2>/dev/null)
BOWER_VERSION := $(shell bower --version 2>/dev/null)
GIT_REVISION := $(shell git rev-parse --short HEAD)

check:
ifndef NPM_VERSION
	$(error npm not found. Install from nodejs.org or see README)
endif
ifndef BOWER_VERSION
	@echo "bower not found. Installing:";
	npm install -g bower
endif

test: check
	./node_modules/karma/bin/karma start

single-test: check
	./node_modules/karma/bin/karma start --single-run

deploy:
	appcfg.py -A $(APP_ID)--oauth2 update app.yaml highend.yaml --version $(GIT_REVISION)

# This is necesary if dispatch rules are updated or for new deployments.
deploy-dispatch:
	appcfg.py -A $(APP_ID) --oauth2 update_dispatch --version $(GIT_REVISION)

# This is necesary if index definition is updated or for new deployments.
deploy-index:
	appcfg.py -A $(APP_ID) --oauth2 update_index --version $(GIT_REVISION)


.PHONY: check test single-test
