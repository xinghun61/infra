// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build !windows

package fifo

import (
	"bytes"
	"io"
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"
)

func TestNewCopier(t *testing.T) {
	t.Parallel()
	d, err := ioutil.TempDir("", "test")
	if err != nil {
		t.Fatalf("Error creating temp dir: %s", err)
	}
	defer os.RemoveAll(d)
	p := filepath.Join(d, "fifo")
	var b bytes.Buffer
	fc, err := NewCopier(&b, p)
	if err != nil {
		t.Fatalf("NewCopier returned error: %s", err)
	}
	defer fc.Close()
	w, err := os.OpenFile(p, os.O_WRONLY, 0666)
	if err != nil {
		t.Fatalf("Error opening fifo %s for write: %s", p, err)
	}
	defer w.Close()
	want := "yuudachi"
	if _, err := io.WriteString(w, want); err != nil {
		t.Fatalf("Error writing: %s", err)
	}
	if err := w.Close(); err != nil {
		t.Fatalf("Error closing fifo writer: %s", err)
	}
	_ = fc.Close() // does not return errors
	got := b.String()
	if got != want {
		t.Errorf("b.String() = %#v; want %#v", got, want)
	}
}
