// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package builder implement local build process.
package builder

import (
	"context"
	"io/ioutil"
	"os"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"

	"infra/cmd/cloudbuildhelper/fileset"
	"infra/cmd/cloudbuildhelper/manifest"
)

// Builder executes local build steps.
type Builder struct {
	tmpDir string
}

// New initializes a builder, allocating a temp directory for it.
func New() (*Builder, error) {
	tmpDir, err := ioutil.TempDir("", "cloudbuildhelper")
	if err != nil {
		return nil, errors.Annotate(err, "failed to allocate a temporary directory").Err()
	}
	return &Builder{tmpDir: tmpDir}, nil
}

// Close removes all temporary files held by this Builder.
//
// Closing the builder invalidates all outputs it ever produced, thus this
// should be done only after outputs are processed.
//
// Idempotent.
func (b *Builder) Close() error {
	if b.tmpDir != "" {
		if err := os.RemoveAll(b.tmpDir); err != nil {
			return errors.Annotate(err, "failed to remove builder temp dir").Err()
		}
		b.tmpDir = ""
	}
	return nil
}

// Build executes all local builds steps specified in the manifest.
//
// The result of this process is a fully populated fileset.Set with all files
// that should be sent to a remote builder.
//
// The returned fileset should not outlive Builder, since it may reference
// temporary files owned by Builder.
func (b *Builder) Build(ctx context.Context, m *manifest.Manifest) (*fileset.Set, error) {
	logging.Debugf(ctx, "Starting the local build using temp dir %q", b.tmpDir)

	out := &fileset.Set{}

	if m.ContextDir != "" {
		logging.Debugf(ctx, "Adding %q to the output set...", m.ContextDir)
		if err := out.AddFromDisk(m.ContextDir, "."); err != nil {
			return nil, errors.Annotate(err, "failed to add contextdir %q to output set", m.ContextDir).Err()
		}
	}

	// TODO(vadimsh): Interpret build steps specified in the manifest.

	return out, nil
}
