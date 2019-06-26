# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Several commands here assume that the Go environment is set up,
# e.g. by running `eval $(infra/go/env.py)`.

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' < Makefile

build:
	cd ../../../go.chromium.org/luci/web && ./web.py build rpcexplorer
	cd frontend/ui && make build

deploy_prod: build
	# Use gcloud app commands instead of appcfg.py; see crbug.com/978627.
	# This will become default later so the LUCI_PY_USE_GCLOUD=1
	# can be removed after crbug.com/835919 is fixed.
	LUCI_PY_USE_GCLOUD=1 gae.py upload --switch --app-id=tricium-prod

deploy_dev: build
	LUCI_PY_USE_GCLOUD=1 gae.py upload --switch --app-id=tricium-dev
