// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"io/ioutil"
	"os"
	"time"

	"github.com/dustin/go-humanize"
	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"

	"infra/cmd/cloudbuildhelper/fileset"
	"infra/cmd/cloudbuildhelper/manifest"
	"infra/cmd/cloudbuildhelper/storage"
)

var cmdBuild = &subcommands.Command{
	UsageLine: "build <target-manifest-path> [...]",
	ShortDesc: "builds a docker image using Google Cloud Build",
	LongDesc: `Builds a docker image using Google Cloud Build.

TODO(vadimsh): Write mini doc.
`,

	CommandRun: func() subcommands.CommandRun {
		c := &cmdBuildRun{}
		c.init()
		return c
	},
}

type cmdBuildRun struct {
	commandBase

	targetManifest string
	infra          string
}

func (c *cmdBuildRun) init() {
	c.commandBase.init(c.exec, true, []*string{
		&c.targetManifest,
	})
	c.Flags.StringVar(&c.infra, "infra", "dev", "What section to pick from 'infra' field in the YAML.")
}

func (c *cmdBuildRun) exec(ctx context.Context) error {
	m, err := readManifest(c.targetManifest)
	if err != nil {
		return err
	}

	infra, ok := m.Infra[c.infra]
	if !ok {
		return errBadFlag("-infra", fmt.Sprintf("no %q infra specified in the manifest", c.infra))
	}
	if infra.Storage == "" {
		return errors.Reason("infra[...].storage is required when using remote build").Tag(isCLIError).Err()
	}

	// Need a token source to talk to Google Storage and Cloud Build.
	ts, err := c.tokenSource(ctx)
	if err != nil {
		return errors.Annotate(err, "failed to setup auth").Err()
	}

	// Instantiate infra services based on what's in the manifest.
	store, err := storage.New(ctx, infra.Storage, ts)
	if err != nil {
		return errors.Annotate(err, "failed to initialize Storage").Err()
	}

	return stage(ctx, m, func(out *fileset.Set) error {
		return remoteBuild(ctx, remoteBuildParams{
			Manifest: m,
			Out:      out,
			Store:    store,
		})
	})
}

// storageImpl is implemented by *storage.Storage.
type storageImpl interface {
	Check(ctx context.Context, name string) (*storage.Object, error)
	Upload(ctx context.Context, name, digest string, r io.Reader) (*storage.Object, error)
}

// remoteBuildParams are passed to remoteBuild.
type remoteBuildParams struct {
	// Inputs.
	Manifest *manifest.Manifest // original manifest
	Out      *fileset.Set       // result of local build stage

	// Infra.
	Store storageImpl // where to upload the tarball, mocked in tests
}

// remoteBuild executes high level remote build logic.
//
// It takes locally built fileset, uploads it to the storage (if necessary)
// and invokes remote builder (if necessary).
func remoteBuild(ctx context.Context, p remoteBuildParams) error {
	logging.Infof(ctx, "Writing tarball with %d files to a temp file to calculate its hash...", p.Out.Len())
	f, digest, err := writeToTemp(p.Out)
	if err != nil {
		return errors.Annotate(err, "failed to write the tarball with context dir").Err()
	}
	size, err := f.Seek(0, 1)
	if err != nil {
		return errors.Annotate(err, "failed to query the size of the temp file").Err()
	}
	logging.Infof(ctx, "Tarball digest: %s", digest)
	logging.Infof(ctx, "Tarball length: %s", humanize.Bytes(uint64(size)))

	// Cleanup no matter what. Note that we don't care about IO flush errors in
	// f.Close() as long as uploadToStorage sent everything successfully (as
	// verified by checking the hash there).
	defer func() {
		f.Close()
		os.Remove(f.Name())
	}()

	// Upload the tarball (or grab metadata of existing object).
	obj, err := uploadToStorage(ctx, p.Store,
		fmt.Sprintf("%s/%s.tar.gz", p.Manifest.Name, digest),
		digest, f)
	if err != nil {
		return err // annotated already
	}

	// Dump metadata into the log, just FYI.
	obj.Log(ctx)

	// TODO(vadimsh): Examine metadata to find references to existing artifacts
	// built from this tarball.

	// TODO(vadimsh): Trigger Cloud Build job to "transform" the uploaded
	// tarball into a docker image.

	return nil
}

// writeToTemp saves the fileset.Set as a temporary *.tar.gz file, returning it
// and its SHA256 hex digest.
//
// The file is opened in read/write mode. The caller is responsible for closing
// and deleting it when done.
func writeToTemp(out *fileset.Set) (*os.File, string, error) {
	f, err := ioutil.TempFile("", "cloudbuildhelper_*.tar.gz")
	if err != nil {
		return nil, "", err
	}
	h := sha256.New()
	if err := out.ToTarGz(io.MultiWriter(f, h)); err != nil {
		f.Close()
		os.Remove(f.Name())
		return nil, "", err
	}
	return f, hex.EncodeToString(h.Sum(nil)), nil
}

// uploadToStorage uploads the given file to the storage if it's not there yet.
func uploadToStorage(ctx context.Context, s storageImpl, obj, digest string, f *os.File) (*storage.Object, error) {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Minute)
	defer cancel()

	switch uploaded, err := s.Check(ctx, obj); {
	case err != nil:
		return nil, errors.Annotate(err, "failed to query the storage for presence of uploaded tarball").Err()
	case uploaded != nil:
		return uploaded, nil
	}

	// Rewind the temp file we have open in read/write mode.
	if _, err := f.Seek(0, 0); err != nil {
		return nil, errors.Annotate(err, "failed to seek inside the temp file").Err()
	}

	uploaded, err := s.Upload(ctx, obj, digest, f)
	return uploaded, errors.Annotate(err, "failed to upload the tarball").Err()
}
