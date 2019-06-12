// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testutils

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"
)

// CreateTempDirOrDie creates a temporary directory.
//
// This function returns the path to the created directory and a cleanup
// function that should be deferred by the caller.
// This function panics on error.
func CreateTempDirOrDie(t *testing.T) (string, func()) {
	t.Helper()
	dir, err := ioutil.TempDir("", "testTempDir")
	if err != nil {
		panic(err)
	}
	return dir, func() {
		os.RemoveAll(dir)
	}
}

// CreateFileOrDie creates a file with the given text.
//
// This function returns the path to the created file.
// This function panics on error.
func CreateFileOrDie(t *testing.T, path []string, text string) string {
	file := path[len(path)-1]
	dir := filepath.Join(path[:len(path)-1]...)
	if err := os.MkdirAll(dir, 0750); err != nil {
		panic(err)
	}
	if err := ioutil.WriteFile(filepath.Join(dir, file), []byte(text), 0640); err != nil {
		panic(err)
	}
	return filepath.Join(dir, file)
}
