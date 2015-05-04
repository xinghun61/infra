# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
projdir := $(patsubst %/,%,$(dir $(mkfile_path)))

vulcanize: $(projdir)/html/main.html
	mkdir -p $(projdir)/gen
	$(projdir)/../third_party/npm_modules/node_modules/vulcanize/bin/vulcanize --abspath html html/main.html -o vulcanized_main.html

deploy: vulcanize
	$(projdir)/tools/gae upload
