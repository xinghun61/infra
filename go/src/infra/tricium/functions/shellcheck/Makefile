# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

SRCS := $(wildcard *.go runner/*.go)

.PHONY: all clean

all: shellcheck_tricium bin

shellcheck_tricium: $(SRCS)
	go build -o shellcheck_tricium

bin:
	./fetch_shellcheck.sh

test: bin
	go test .

testrun: shellcheck_tricium bin
	./shellcheck_tricium -input=testdata -output=testout -path_filters="*.sh"

clean:
	rm -rf shellcheck-*.tbz2 shellcheck-*.xz shellcheck_tricium bin testout
