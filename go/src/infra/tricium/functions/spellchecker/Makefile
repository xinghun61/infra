# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

.PHONY: test python codespell

spellchecker: python codespell
	go build -o spellchecker

test: spellchecker
	./spellchecker -input=test -output=test-out

spellchecker.cipd: spellchecker python codespell
	cipd pkg-build -pkg-def cipd.yaml -out spellchecker.cipd

python:
	cipd install -root python infra/python/cpython/linux-amd64

codespell:
	PYTHONUSERBASE=codespell pip install --ignore-installed --user codespell

clean:
	rm -rf codespell pylint.cipd python spellchecker out
