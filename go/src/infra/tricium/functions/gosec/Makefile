# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

.PHONY: test clean

gosecwrapper: gosec
	go build -o gosecwrapper

test: gosecwrapper
	./gosecwrapper -input=test -output=out && go test || echo "TEST FAILED"

clean:
	rm -rf ./bin gosecwrapper

gosec:
	if [ ! -d ./bin ] ; then mkdir bin && curl -sfL https://raw.githubusercontent.com/securego/gosec/master/install.sh | sh -s latest; fi

cipd:
	cipd create -pkg-def=cipd.yaml
	cipd set-ref infra/tricium/function/gosec -ref live -version latest

