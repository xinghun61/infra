// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package atutil

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"
)

func TestLinkFile(t *testing.T) {
	t.Parallel()
	tmp, err := ioutil.TempDir("", "os_test")
	if err != nil {
		t.Fatalf("Error creating temp dir: %s", err)
	}
	defer os.RemoveAll(tmp)
	a := filepath.Join(tmp, "foo")
	b := filepath.Join(tmp, "bar")
	if err := ioutil.WriteFile(a, []byte("foo"), 0700); err != nil {
		t.Fatalf("Error writing test file: %s", err)
	}

	if err := linkFile(a, b); err != nil {
		t.Fatalf("Error calling linkFile: %s", err)
	}

	ai, err := os.Stat(a)
	if err != nil {
		t.Fatalf("Error calling stat: %s", err)
	}
	bi, err := os.Stat(b)
	if err != nil {
		t.Fatalf("Error calling stat: %s", err)
	}
	if !os.SameFile(ai, bi) {
		t.Errorf("%s and %s are not the same file", a, b)
	}
}
