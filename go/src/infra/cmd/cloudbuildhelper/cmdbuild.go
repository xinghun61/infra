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
	"path"
	"time"

	"github.com/dustin/go-humanize"
	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag/stringmapflag"
	"go.chromium.org/luci/common/logging"

	"infra/cmd/cloudbuildhelper/cloudbuild"
	"infra/cmd/cloudbuildhelper/docker"
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
	labels         stringmapflag.Value
}

func (c *cmdBuildRun) init() {
	c.commandBase.init(c.exec, true, []*string{
		&c.targetManifest,
	})
	c.Flags.StringVar(&c.infra, "infra", "dev", "What section to pick from 'infra' field in the YAML.")
	c.Flags.Var(&c.labels, "label", "Labels to attach to the docker image, in k=v form.")
}

func (c *cmdBuildRun) exec(ctx context.Context) error {
	m, err := readManifest(c.targetManifest)
	if err != nil {
		return err
	}

	infra, ok := m.Infra[c.infra]
	switch {
	case !ok:
		return errBadFlag("-infra", fmt.Sprintf("no %q infra specified in the manifest", c.infra))
	case infra.Storage == "":
		return errors.Reason("in %q: infra[...].storage is required when using remote build", c.targetManifest).Tag(isCLIError).Err()
	case infra.CloudBuild.Project == "":
		return errors.Reason("in %q: infra[...].cloudbuild.project is required when using remote build", c.targetManifest).Tag(isCLIError).Err()
	}

	// Need a token source to talk to Google Storage and Cloud Build.
	ts, err := c.tokenSource(ctx)
	if err != nil {
		return errors.Annotate(err, "failed to setup auth").Err()
	}

	// Instantiate infra services based on what's in the manifest.
	store, err := storage.New(ctx, ts, infra.Storage)
	if err != nil {
		return errors.Annotate(err, "failed to initialize Storage").Err()
	}
	builder, err := cloudbuild.New(ctx, ts, infra.CloudBuild)
	if err != nil {
		return errors.Annotate(err, "failed to initialize Builder").Err()
	}

	return stage(ctx, m, func(out *fileset.Set) error {
		_, err := remoteBuild(ctx, remoteBuildParams{
			Manifest: m,
			Out:      out,
			Registry: infra.Registry,
			Labels:   c.labels,
			Store:    store,
			Builder:  builder,
		})
		return err
	})
}

// storageImpl is implemented by *storage.Storage.
type storageImpl interface {
	Check(ctx context.Context, name string) (*storage.Object, error)
	Upload(ctx context.Context, name, digest string, r io.Reader) (*storage.Object, error)
}

// builderImpl is implemented by *cloudbuild.Builder.
type builderImpl interface {
	Trigger(ctx context.Context, r cloudbuild.Request) (*cloudbuild.Build, error)
	Check(ctx context.Context, bid string) (*cloudbuild.Build, error)
}

// remoteBuildParams are passed to remoteBuild.
type remoteBuildParams struct {
	// Inputs.
	Manifest *manifest.Manifest // original manifest
	Out      *fileset.Set       // result of local build stage
	Registry string             // registry to upload the image to (if any)
	Labels   map[string]string  // extra labels to put into the image

	// Infra.
	Store   storageImpl // where to upload the tarball, mocked in tests
	Builder builderImpl // where to build images, mocked in tests
}

// remoteBuildResult is returned by remoteBuild.
type remoteBuildResult struct {
	Image  string // name of the uploaded image
	Digest string // docker digest of the uploaded image
}

// remoteBuild executes high level remote build logic.
//
// It takes locally built fileset, uploads it to the storage (if necessary)
// and invokes Cloud Build builder (if necessary).
func remoteBuild(ctx context.Context, p remoteBuildParams) (*remoteBuildResult, error) {
	logging.Infof(ctx, "Writing tarball with %d files to a temp file to calculate its hash...", p.Out.Len())
	f, digest, err := writeToTemp(p.Out)
	if err != nil {
		return nil, errors.Annotate(err, "failed to write the tarball with context dir").Err()
	}
	size, err := f.Seek(0, 1)
	if err != nil {
		return nil, errors.Annotate(err, "failed to query the size of the temp file").Err()
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
		return nil, err // annotated already
	}

	// Dump metadata into the log, just FYI.
	obj.Log(ctx)

	// TODO(vadimsh): Examine metadata to find references to existing artifacts
	// built from this tarball.

	// If not using a registry, just build and then discard the image. This is
	// accomplished by NOT passing an image name to cloudbuild.Builder.
	imageName := ""
	if p.Registry != "" {
		imageName = path.Join(p.Registry, p.Manifest.Name)
	}

	// Trigger Cloud Build build to "transform" the tarball into a docker image.
	imageDigest, err := performBuild(ctx, p.Builder, imageName, obj, digest, p.Labels)
	if err != nil {
		return nil, err // annotated already
	}
	if imageName == "" {
		logging.Warningf(ctx, "The registry is not configured, the image wasn't pushed")
		return &remoteBuildResult{}, nil
	}

	// Success!
	logging.Infof(ctx, "The produced image:")
	logging.Infof(ctx, "    Name:   %s", imageName)
	logging.Infof(ctx, "    Digest: %s", imageDigest)
	logging.Infof(ctx, "    View:   https://%s@%s", imageName, imageDigest)

	// TODO(vadimsh): Tag the image.
	// TODO(vadimsh): Add -json-output.

	return &remoteBuildResult{Image: imageName, Digest: imageDigest}, nil
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

// performBuild builds and pushes (but not tags) a docker image via Cloud Build.
//
// 'image' is a full image name (including the registry) to build and push or
// an empty string just to build and then discard the image.
//
// 'in' is a tarball with the context directory, 'inDigest' is its SHA256 hash.
//
// On success returns "sha256:..." digest of the built and pushed image.
func performBuild(ctx context.Context, bldr builderImpl, image string, in *storage.Object, inDigest string, labels map[string]string) (string, error) {
	logging.Infof(ctx, "Triggering new Cloud Build build...")

	// Cloud Build always pushes the tagged image to the registry. The default tag
	// is "latest", and we don't want to use it in case someone decides to rely
	// on it. So pick something more cryptic. Note that we don't really care if
	// this tag is moved concurrently by someone else. We never read it, we
	// consume only the image digest returned directly by Cloud Build API.
	if image != "" {
		image += ":cbh"
	}
	build, err := bldr.Trigger(ctx, cloudbuild.Request{
		Source: in,
		Image:  image,
		Labels: docker.Labels{
			Created:   clock.Now(ctx).UTC(),
			BuildTool: userAgent,
			BuildMode: "cloudbuild",
			Inputs:    inDigest,
			Extra:     labels,
		},
	})
	if err != nil {
		return "", errors.Annotate(err, "failed to trigger Cloud Build build").Err()
	}
	logging.Infof(ctx, "Triggered build %s", build.ID)
	logging.Infof(ctx, "Logs are available at %s", build.LogURL)

	// Babysit it until it completes.
	logging.Infof(ctx, "Waiting for the build to finish...")
	if build, err = waitBuild(ctx, bldr, build); err != nil {
		return "", errors.Annotate(err, "when waiting for the build to finish").Err()
	}
	if build.Status != cloudbuild.StatusSuccess {
		return "", errors.Reason("build failed, see its logs at %s", build.LogURL).Err()
	}

	// Make sure Cloud Build worker really consumed the tarball we prepared.
	if got := build.InputHashes[in.String()]; got != inDigest {
		return "", errors.Reason("build consumed file with digest %q, but we produced %q", got, inDigest).Err()
	}
	// And it pushed the image we asked it to push.
	if build.OutputImage != image {
		return "", errors.Reason("build produced image %q, but we expected %q", build.OutputImage, image).Err()
	}

	return build.OutputDigest, nil
}

// waitBuild polls Build until it is in some terminal state (successful or not).
func waitBuild(ctx context.Context, bldr builderImpl, b *cloudbuild.Build) (*cloudbuild.Build, error) {
	errs := 0 // number of errors observed sequentially thus far
	for {
		// Report the status line even if the build is already done, still useful.
		status := string(b.Status)
		if b.StatusDetails != "" {
			status += ": " + b.StatusDetails
		}
		logging.Infof(ctx, "    ... %s", status)

		if b.Status.IsTerminal() {
			return b, nil
		}
		if err := clock.Sleep(clock.Tag(ctx, "sleep-timer"), 5*time.Second).Err; err != nil {
			return nil, err
		}

		build, err := bldr.Check(ctx, b.ID)
		if err != nil {
			if errs++; errs > 5 {
				return nil, errors.Annotate(err, "too many errors, the last one").Err()
			}
			logging.Warningf(ctx, "Error when checking build status - %s", err)
			continue // sleep and try again
		}
		errs = 0

		if build.ID != b.ID {
			return nil, errors.Reason("got unexpected build with ID %q, expecting %q", build.ID, b.ID).Err()
		}
		b = build
	}
}
