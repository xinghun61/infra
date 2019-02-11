// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// vpythonsmoktest runs vpython in parallel to find out if there is any subtle
// race condition.

package main

import (
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
)

// removeAll removes a tree, even for read-only directories.
//
// This is needed because the virtualenv directory created by vpython is setup
// as read-only.
func removeAll(root string) error {
	err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if info.IsDir() {
			return os.Chmod(path, 0777)
		}
		return nil
	})
	if err2 := os.RemoveAll(root); err == nil {
		return err2
	}
	return err
}

func mainImpl(ctx context.Context) error {
	// Create a temporary directory, then run stuff in it.
	root, err := ioutil.TempDir("", "vpythonsmoketest")
	if err != nil {
		return err
	}
	// Clear out any environment variable that would affect vpython behavior.
	os.Setenv("VPYTHON_BYPASS", "")
	os.Setenv("VPYTHON_CLEAR_PYTHONPATH", "")
	os.Setenv("VPYTHON_DEFAULT_SPEC", "")
	os.Setenv("VPYTHON_LOG_TRACE", "")
	// Use a test-local CIPD cache.
	os.Setenv("CIPD_CACHE_DIR", filepath.Join(root, ".cipd"))
	// Use a test-local virtualenv.
	os.Setenv("VPYTHON_VIRTUALENV_ROOT", filepath.Join(root, ".vpython"))

	c := exec.CommandContext(ctx, "vpython", "main.py")
	c.Dir = "testdata"
	c.Stdout = os.Stdout
	c.Stderr = os.Stderr
	err = c.Run()

	// This is important, it may fail on Windows, especially if there is any
	// stray process.
	err2 := removeAll(root)
	if err != nil {
		return err
	}
	if err2 != nil {
		return fmt.Errorf("failed to cleanup! %v", err2)
	}
	return nil
}

func main() {
	// TODO(maruel): Handle Ctrl-C.
	ctx := gologger.StdConfig.Use(logging.SetLevel(context.Background(), logging.Warning))
	if err := mainImpl(ctx); err != nil {
		fmt.Fprintf(os.Stderr, "vpythonsmoketest: %v\n", err)
		os.Exit(1)
	}
}
