# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

.PHONY: test

spellchecker: codespell_dict
	go build -o spellchecker

test: spellchecker
	./spellchecker -input=test -output=out

# Updating the dictionary periodically is a good idea to get new words to check
# but is not necessary.
codespell_dict:
	rm dictionary.txt
	wget https://raw.githubusercontent.com/codespell-project/codespell/master/codespell_lib/data/dictionary.txt

clean:
	rm -rf spellchecker.cipd spellchecker out
