# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

all:
	@echo "Usage:"
	@echo "  make proxy                        - Just builds the proxy binary"
	@echo "  make build-{dev,prod}             - Builds the Docker image"
	@echo "  make deploy-{dev,prod}-{1,2,3}    - Builds and deploys to the GCE instance"

proxy: $(shell find ../../go/src/infra/monitoring/proxy -type f)
	cd ../../go && ./env.py go install -v infra/monitoring/proxy
	mv ../../go/bin/proxy .

build-dev: .build-dev
build-prod: .build-prod
.build-dev .build-prod: proxy monitoring_proxy_containers.yaml.template monitoring_proxy.sh Dockerfile
	./docker_build.sh $(subst .build-,,$@)
	touch $@

deploy-dev-1: .deploy-dev-1
deploy-dev-2: .deploy-dev-2
deploy-dev-3: .deploy-dev-3
.deploy-dev-1 .deploy-dev-2 .deploy-dev-3: .build-dev
	./setup.sh proxy$(subst .deploy-dev-,,$@) dev

deploy-prod-1: .deploy-prod-1
deploy-prod-2: .deploy-prod-2
deploy-prod-3: .deploy-prod-3
.deploy-prod-1 .deploy-prod-2 .deploy-prod-3: .build-prod
	./setup.sh proxy$(subst .deploy-prod-,,$@) prod
