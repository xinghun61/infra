# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

OUT_BASE=eslint-deps

.PHONY: test clean

eslint_parser: eslint
	go build -o eslint_parser

eslint:
	./setup.py

test: eslint_parser
	./eslint_parser -input=test -output=out

clean:
	rm -rf eslint_parser node node_modules node.tar.gz out
