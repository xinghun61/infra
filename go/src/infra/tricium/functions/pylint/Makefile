# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

OUT_BASE=pylint-deps

.PHONY: test clean

pylint_parser: python pylint
	go build -o pylint_parser

test: pylint_parser
	./pylint_parser -input=test -output=out

python:
	cipd install -root python infra/python/cpython/linux-amd64

pylint:
	PYTHONUSERBASE=pylint pip install --ignore-installed --user pylint

clean:
	rm -rf pylint_parser pylint python out
