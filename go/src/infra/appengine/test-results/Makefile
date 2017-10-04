# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Makefile to simplify some common actions.
# Use 'make help' for a list of commands.

.PHONY: help build clean test devserver deploy_staging deploy_prod

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

deploy_staging:
	gae.py upload -A test-results-test-hrd

deploy_prod:
	gae.py upload
