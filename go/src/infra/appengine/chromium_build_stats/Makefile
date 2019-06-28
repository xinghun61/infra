# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

build:
	go build ./...

generate: ninjaproto/ninjalog.proto
	go generate ./...

update-staging: ninjaproto/ninjalog.proto
	bqschemaupdater -message-dir ninjaproto -message ninjaproto.NinjaTask -table chromium-build-stats-staging.ninjalog.ninjalog
	bqschemaupdater -message-dir ninjaproto -message ninjaproto.NinjaTask -table chromium-build-stats-staging.ninjalog.user

# namiko(TODO): change table name later
update-prod: ninjaproto/ninjalog.proto
	bqschemaupdater -message-dir ninjaproto -message ninjaproto.NinjaTask -table chromium-build-stats.ninjalog.ninjalog
	bqschemaupdater -message-dir ninjaproto -message ninjaproto.NinjaTask -table chromium-build-stats.ninjalog.user


deploy-staging:
	gcloud --project=chromium-build-stats-staging app deploy --promote app/app.yaml

deploy-prod:
	gcloud --project=chromium-build-stats app deploy --promote app/app.yaml

test:
	go test ./...
