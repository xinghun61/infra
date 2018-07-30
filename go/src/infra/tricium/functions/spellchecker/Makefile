# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

.PHONY: test

spellchecker: codespell_dict
	go build -o spellchecker

test: spellchecker
	./spellchecker -input=test -output=out

codespell_dict:
	wget https://raw.githubusercontent.com/codespell-project/codespell/master/codespell_lib/data/dictionary.txt

clean:
	rm -rf spellchecker.cipd spellchecker out
