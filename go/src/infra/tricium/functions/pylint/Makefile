# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

OUT_BASE=pylint-deps

.PHONY: test python pylint

pylint_parser: python pylint
	go build -o pylint_parser

test: pylint_parser
	./pylint_parser -input=test -output=test-out

pylint.cipd: pylint_parser python pylint
	cipd pkg-build -pkg-def cipd.yaml -out pylint.cipd

python:
	cipd install -root python infra/python/cpython/linux-amd64

pylint:
	PYTHONUSERBASE=pylint pip install --ignore-installed --user pylint

clean:
	rm pylint_parser || true
	rm -rf pylint || true
	rm -rf python || true
	rm -rf test-out || true
	rm pylint.cipd || true
