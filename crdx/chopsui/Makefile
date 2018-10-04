# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

WCT_DIR = ../../go/src/infra/tools/wct
WCT_GO = $(WCT_DIR)/wct.go $(WCT_DIR)/loader.go
$(eval BASE := $(shell pwd))

wct:
	xvfb-run go run $(WCT_GO) -chrome=google-chrome

wct_debug:
	go run $(WCT_GO) -chrome=google-chrome -persist

# Runs wct.go using a full path for -base, which is what it does
# when it runs on CI.
wct_repro:
	go run $(WCT_GO) --base $(BASE) --chrome=google-chrome --prefix test/