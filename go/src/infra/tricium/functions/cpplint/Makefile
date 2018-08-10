# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

.PHONY: test clean

cpplint_parser: python cpplint.py
	go build -o cpplint_parser

test: cpplint_parser
	./cpplint_parser -input=test -output=out

cpplint.cipd: cpplint_parser python cpplint.py
	cipd pkg-build -pkg-def cipd.yaml -out cpplint.cipd

python:
	cipd install -root python infra/python/cpython/linux-amd64

cpplint.py:
	wget https://raw.githubusercontent.com/google/styleguide/gh-pages/cpplint/cpplint.py
	chmod +x cpplint.py

clean:
	rm -rf cpplint_parser cpplint.py python out cpplint.cipd
