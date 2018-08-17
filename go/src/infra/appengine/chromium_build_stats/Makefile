# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

build:
	go build ./...

generate: ninjalog/ninjalog.proto
	go generate ./...

deploy-staging:
	gae.py upload --app-id chromium-build-stats-staging

deploy-prod:
	gae.py upload --app-id chromium-build-stats

test:
	go test ./...
