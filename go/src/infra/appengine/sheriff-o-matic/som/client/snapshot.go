// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package client

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"golang.org/x/net/context"

	"infra/monitoring/messages"

	"go.chromium.org/luci/common/logging"
)

// NewSnapshot returns a client which will record responses to baseDir for later replay.
func NewSnapshot(wrapped readerType, baseDir string) readerType {
	sc := &snapshot{
		wrapped: wrapped,
		baseDir: baseDir,
	}
	return sc
}

type snapshot struct {
	baseDir string
	wrapped readerType
}

// Build fetches the build summary for master master, builder builder and build id buildNum
// from build.chromium.org.
func (c *snapshot) Build(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error) {
	b, err := c.wrapped.Build(ctx, master, builder, buildNum)
	if err != nil {
		return nil, err
	}
	err = write(filepath.Join(c.baseDir, "build", master.Name(), builder, fmt.Sprintf("%d", buildNum)), b)
	return b, err
}

func (c *snapshot) LatestBuilds(ctx context.Context, master *messages.MasterLocation, builder string) ([]*messages.Build, error) {
	bs, err := c.wrapped.LatestBuilds(ctx, master, builder)
	if err != nil {
		return nil, err
	}

	err = write(filepath.Join(c.baseDir, "latestbuilds", master.Name(), builder), bs)
	if err != nil {
		return nil, err
	}
	for _, b := range bs {
		if err := write(filepath.Join(c.baseDir, "build", master.Name(), builder, fmt.Sprintf("%d", b.Number)), b); err != nil {
			return nil, err
		}
	}
	return bs, err
}

// BuildExtracts fetches build information for masters from CBE in parallel.
// Returns a map of url to error for any requests that had errors.
func (c *snapshot) BuildExtract(ctx context.Context, master *messages.MasterLocation) (*messages.BuildExtract, error) {
	m, err := c.wrapped.BuildExtract(ctx, master)
	if err != nil {
		return nil, err
	}
	err = write(filepath.Join(c.baseDir, "buildextracts", master.Name()), m)
	if err != nil {
		logging.Errorf(ctx, "Error snapshotting build extract: %v", err)
	}
	return m, err
}

// StdioForStep fetches the standard output for a given build step, and an error if any
// occurred.
func (c *snapshot) StdioForStep(ctx context.Context, master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error) {
	s, err := c.wrapped.StdioForStep(ctx, master, builder, step, buildNum)
	if err != nil {
		return nil, err
	}
	err = write(filepath.Join(c.baseDir, "stdioforstep", master.Name(), builder, step, fmt.Sprintf("%d", buildNum)), s)
	return s, err
}

func (c *snapshot) CrbugItems(ctx context.Context, label string) ([]messages.CrbugItem, error) {
	items, err := c.wrapped.CrbugItems(ctx, label)
	if err != nil {
		return nil, err
	}
	err = write(filepath.Join(c.baseDir, "crbugitems", label), items)
	if err != nil {
		logging.Errorf(ctx, "Error snapshotting crbug items: %v", err)
	}
	return items, err
}

func (c *snapshot) Findit(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error) {
	items, err := c.wrapped.Findit(ctx, master, builder, buildNum, failedSteps)
	if err != nil {
		return nil, err
	}
	// Ignore failedSteps since we assume only one call per build
	err = write(filepath.Join(c.baseDir, "findit", master.Name(), builder, fmt.Sprintf("%d", buildNum)), items)
	if err != nil {
		logging.Errorf(ctx, "Error snapshotting findit: %v", err)
	}
	return items, err
}

// TODO(seanmccullough): Evaluate GOB encoding as a faster alternative.
func write(path string, v interface{}) error {
	err := os.MkdirAll(filepath.Dir(path), 0777)
	if err != nil {
		return err
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}

	defer f.Close()

	enc := json.NewEncoder(f)
	err = enc.Encode(v)
	return err
}
