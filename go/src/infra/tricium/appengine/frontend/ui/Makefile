# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

.PHONY: build serve test lint
POLYMER = node_modules/.bin/polymer
ESLINT = node_modules/.bin/eslint

# TODO(qyearsley): Investigate making this work with
# the Go WCT runner and allowing tests to be run on CI.
# See the Monorail Makefile. This may require resolving
# "bare paths" that are used here, and this might have
# to be done by "building" the tests first.

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' < Makefile

node_modules:
	npm install

build: node_modules
	$(POLYMER) build

serve: node_modules
	$(POLYMER) serve

test: node_modules
	$(POLYMER) test

lint: node_modules
	$(POLYMER) lint
	$(ESLINT) src/*.js
	$(ESLINT) test/*.html
