// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package system

import (
	"io/ioutil"
	"strings"
)

const (
	nodevPrefix = "nodev\t"
)

var (
	fstypeBlacklist map[string]struct{}
)

func isBlacklistedFstype(fstype string) bool {
	if strings.HasPrefix(fstype, "fuse.") || fstype == "none" {
		return true
	}

	if fstypeBlacklist == nil {
		fstypeBlacklist = map[string]struct{}{}
		contents, err := ioutil.ReadFile("/proc/filesystems")
		if err != nil {
			return false
		}

		lines := strings.Split(string(contents), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, nodevPrefix) {
				fstypeBlacklist[line[len(nodevPrefix):]] = struct{}{}
			}
		}
	}

	_, ok := fstypeBlacklist[fstype]
	return ok
}
