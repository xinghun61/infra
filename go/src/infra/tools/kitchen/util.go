// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"go.chromium.org/luci/common/errors"
	log "go.chromium.org/luci/common/logging"
	grpcLogging "go.chromium.org/luci/grpc/logging"
)

func encodeJSONToPath(path string, obj interface{}) (err error) {
	fd, err := os.Create(path)
	if err != nil {
		return errors.Annotate(err, "failed to create output file").Err()
	}
	defer func() {
		closeErr := fd.Close()
		if closeErr != nil && err == nil {
			err = errors.Annotate(closeErr, "failed to close output file").Err()
		}
	}()
	if err = json.NewEncoder(fd).Encode(obj); err != nil {
		return errors.Annotate(err, "failed to write encoded object").Err()
	}
	return nil
}

// ensureDir ensures dir at path exists.
// Returned errors are annotated.
func ensureDir(path string) error {
	if err := os.MkdirAll(path, 0755); err != nil && !os.IsExist(err) {
		return errors.Annotate(err, "could not create temp dir %q", path).Err()
	}
	return nil
}

// dirHashFiles returns true if the directory contains files/subdirectories.
// If it does not exist, return an os.IsNonExist error.
func dirHasFiles(path string) (bool, error) {
	dir, err := os.Open(path)
	if err != nil {
		return false, err
	}
	defer dir.Close()

	names, err := dir.Readdirnames(1)
	if err != nil && err != io.EOF {
		return false, errors.Annotate(err, "could not read dir %q", path).Err()
	}

	return len(names) > 0, nil
}

// printCommand prints cmd description to stdout and that it will be ran.
// panics if cannot read current directory or cannot make a command's current
// directory absolute.
func printCommand(ctx context.Context, cmd *exec.Cmd) {
	log.Infof(ctx, "running %q", cmd.Args)
	log.Infof(ctx, "command path: %s", cmd.Path)

	cd := cmd.Dir
	if cd == "" {
		var err error
		cd, err = os.Getwd()
		if err != nil {
			fmt.Fprintf(os.Stderr, "could not read working directory: %s\n", err)
			cd = ""
		}
	}
	if cd != "" {
		abs, err := filepath.Abs(cd)
		if err != nil {
			fmt.Fprintf(os.Stderr, "could not make path %q absolute: %s\n", cd, err)
		} else {
			log.Infof(ctx, "current directory: %s", abs)
		}
	}

	// Log env.
	envLines := strings.Builder{}
	for _, e := range cmd.Env {
		envLines.WriteString("\n\t")
		envLines.WriteString(e)
	}
	log.Infof(ctx, "env:%s", envLines.String())
}

// nonCancelContext is a context.Context which deliberately ignores cancellation
// installed in its parent Contexts. This is used to shield the LogDog output
// from having its operations cancelled if the supplied Context is cancelled,
// allowing it to flush.
type nonCancelContext struct {
	base  context.Context
	doneC chan struct{}
}

func withNonCancel(ctx context.Context) context.Context {
	return &nonCancelContext{
		base:  ctx,
		doneC: make(chan struct{}),
	}
}

func (c *nonCancelContext) Deadline() (time.Time, bool)       { return time.Time{}, false }
func (c *nonCancelContext) Done() <-chan struct{}             { return c.doneC }
func (c *nonCancelContext) Err() error                        { return nil }
func (c *nonCancelContext) Value(key interface{}) interface{} { return c.base.Value(key) }

// callbackReadCloser invokes a callback method when closed.
type callbackReadCloser struct {
	io.ReadCloser
	callback func()
}

func (c *callbackReadCloser) Close() error {
	defer c.callback()
	return c.ReadCloser.Close()
}

// disableGRPCLogging routes gRPC log messages that are emitted through our
// logger. We only log gRPC prints if our logger is configured to log
// debug-level or lower, which it isn't by default.
func disableGRPCLogging(ctx context.Context) {
	level := log.Debug
	if !log.IsLogging(ctx, log.Debug) {
		level = grpcLogging.Suppress
	}
	grpcLogging.Install(log.Get(ctx), level)
}
