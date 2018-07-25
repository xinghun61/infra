# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

OUT_BASE=pylint-deps

.PHONY: test python cpplint.py cpplint_parser

cpplint_parser: python cpplint
	go build -o cpplint_parser

test: cpplint_parser
	./cpplint_parser -input=test -output=test-out

cpplint.cipd: cpplint_parser python cpplint
	cipd pkg-build -pkg-def cipd.yaml -out cpplint.cipd

python:
	cipd install -root python infra/python/cpython/linux-amd64

cpplint:
	rm cpplint.py
	wget https://raw.githubusercontent.com/google/styleguide/gh-pages/cpplint/cpplint.py
	chmod +x cpplint.py

clean:
	rm -rf pylint_parser cpplint.py python test cpplint.cipd
