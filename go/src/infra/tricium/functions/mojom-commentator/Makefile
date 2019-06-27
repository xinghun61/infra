# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

.PHONY: test clean

mojom-commentator:
	go build

test: mojom-commentator
	./mojom-commentator -input=test -output=out

clean:
	rm -rf out mojom-commentator
