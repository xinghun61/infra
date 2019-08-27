# Copyright 2018 The LUCI Authors. All rights reserved.
# Use of this source code is governed under the Apache License, Version 2.0
# that can be found in the LICENSE file.

mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
projdir := $(patsubst %/,%,$(dir $(mkfile_path)))
bindir := $(projdir)/bin
servercmd := $(bindir)/qscheduler-swarming

# Cloud Project to build and store the docker images in.
#
# We use qscheduler-swarming to store images for both dev and prod deployments
# (since we want to test *exact same* image we deploy to prod).
#
# TODO(vadimsh): Revisit this decision. For example, we can have a dedicated
# Cloud Project to store Chops-owned images. A single project makes automation
# simpler.
CLOUD_BUILD_PROJECT = qscheduler-swarming

test:
	go test ./...

gen:
	go generate ./...

# GKE specific commands.

run-local:
	go run $(projdir)/cmd/qscheduler-swarming/main.go \
		-qscheduler-config $(projdir)/devcfg/services/dev/config.cfg \
		-cloud-project qscheduler-swarming-dev \
		-http-addr "0.0.0.0:8082" \
		-admin-addr "0.0.0.0:8900"

.setup-bindir:
	rm -rf $(bindir)
	mkdir -p $(bindir)

build-server-binary: .setup-bindir
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -v \
		-o $(servercmd) \
		$(projdir)/cmd/qscheduler-swarming \

build-docker-image: build-server-binary
	cp $(projdir)/cmd/qscheduler-swarming/Dockerfile $(bindir)/
	gcloud builds submit \
		--tag gcr.io/$(CLOUD_BUILD_PROJECT)/qscheduler-swarming \
		--project $(CLOUD_BUILD_PROJECT) \
		$(bindir)
