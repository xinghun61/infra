// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package atutil

import (
	"os"
)

// appendToFile appends a string to a file.
// The file is not created if it does not exist.
func appendToFile(path string, s string) error {
	f, err := os.OpenFile(path, os.O_APPEND|os.O_WRONLY, 0666)
	if err != nil {
		return err
	}
	defer f.Close()
	if _, err = f.WriteString(s); err != nil {
		return err
	}
	return nil
}

// linkFile creates a link to src at dst, removing dst first if it
// exists.
func linkFile(src string, dst string) error {
	if sameFile(src, dst) {
		return nil
	}
	_ = os.Remove(dst)
	return os.Link(src, dst)
}

// sameFile returns true if a and b are the same file.  This function
// returns false if an error occurred (e.g., permission or
// nonexistent).
func sameFile(a string, b string) bool {
	ai, err := os.Stat(a)
	if err != nil {
		return false
	}
	bi, err := os.Stat(b)
	if err != nil {
		return false
	}
	return os.SameFile(ai, bi)
}
