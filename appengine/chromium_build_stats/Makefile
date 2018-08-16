# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

build:
	cd default; ../goenv.sh goapp build

generate: gopath/src/ninjalog/ninjalog.proto
	go generate ./...

deploy-staging:
	./goenv.sh goapp deploy --application chromium-build-stats-staging --version $(shell git log -1 --pretty=format:git-%H) default

deploy-prod:
	./goenv.sh goapp deploy --application chromium-build-stats --version $(shell git log -1 --pretty=format:git-%H) default

test:
	cd default; ../goenv.sh goapp test
