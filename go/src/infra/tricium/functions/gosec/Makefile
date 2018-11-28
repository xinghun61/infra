# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

.PHONY: test clean

gosec_wrapper: gosec
	go build -o gosec_wrapper

test: gosec_wrapper
	./gosec_wrapper -input=test -output=out && go test || echo "TEST FAILED"

clean:
	rm -rf bin out gosec_wrapper

gosec:
	if [ ! -d ./bin ] ; then mkdir bin && curl -sfL https://raw.githubusercontent.com/securego/gosec/master/install.sh | sh -s latest; fi
