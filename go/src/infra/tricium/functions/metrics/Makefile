# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

.PHONY: test clean

histograms-check:
	go build -o histograms_check

test: histograms-check
	./histograms_check -input=test -output=out

unit-test:
	go test histograms_check_test.go histograms_check.go

clean:
	rm -rf out histograms-check