# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

.PHONY: test clean

commitcheck:
	go build -o commitcheck

test: commitcheck
	./commitcheck -input=test -output=out

clean:
	rm -rf out commitcheck
