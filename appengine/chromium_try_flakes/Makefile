# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Makefile to simplify some common AppEngine actions.
# Use 'make help' for a list of commands.
GAE_PY?= python gae.py

help:
	@echo "Supported commands: deploy_staging deploy_prod"

deploy_staging:
	$(GAE_PY) upload -A chromium-try-flakes-staging -f

deploy_prod:
	$(GAE_PY) upload -A chromium-try-flakes
