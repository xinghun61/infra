# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

build:
	go build ./...

generate: ninjaproto/ninjalog.proto
	go generate ./...

update-staging: ninjaproto/ninjalog.proto
	bqschemaupdater -message-dir ninjaproto -message ninjaproto.NinjaTask -table chromium-build-stats-staging.ninjalog.staging

# namiko(TODO): change table name later
update-prod: ninjaproto/ninjalog.proto
	bqschemaupdater -message-dir ninjaproto -message ninjaproto.NinjaTask -table chromium-build-stats.ninjalog.staging

deploy-staging:
	gae.py upload --app-id chromium-build-stats-staging --app-dir=app/

deploy-prod:
	gae.py upload --app-id chromium-build-stats --app-dir=app/

test:
	go test ./...
