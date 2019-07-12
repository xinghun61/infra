# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

.PHONY: test clean

pylint_parser: python pylint
	go build -o pylint_parser

test: pylint_parser
	./pylint_parser -input=test -output=out

python:
	cipd install -root python infra/python/cpython/linux-amd64

pylint:
	# The following command fails when the vpython pip is used,
	# but the pip from the python fetched doesn't work; instead,
	# for now, depend on a system-wide pip. See crbug.com/983222.
	PYTHONUSERBASE=pylint /usr/bin/pip install --ignore-installed --user pylint

clean:
	rm -rf pylint_parser pylint python out
