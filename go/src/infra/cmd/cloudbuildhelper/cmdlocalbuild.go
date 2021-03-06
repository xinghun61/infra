// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"io"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag/stringmapflag"
	"go.chromium.org/luci/common/logging"

	"infra/cmd/cloudbuildhelper/docker"
	"infra/cmd/cloudbuildhelper/fileset"
	"infra/cmd/cloudbuildhelper/manifest"
)

var cmdLocalBuild = &subcommands.Command{
	UsageLine: "localbuild <target-manifest-path> [...]",
	ShortDesc: "builds a docker image using local docker daemon",
	LongDesc: `Builds a docker image using local docker daemon.

Roughly does "docker build --no-cache --squash --tag <name> <context>", where
<name> and <context> come from the manifest.

Doesn't upload the image anywhere.
`,

	CommandRun: func() subcommands.CommandRun {
		c := &cmdLocalBuildRun{}
		c.init()
		return c
	},
}

type cmdLocalBuildRun struct {
	commandBase

	targetManifest string
	labels         stringmapflag.Value
}

func (c *cmdLocalBuildRun) init() {
	c.commandBase.init(c.exec, false, []*string{
		&c.targetManifest,
	})
	c.Flags.Var(&c.labels, "label", "Labels to attach to the docker image, in k=v form.")
}

func (c *cmdLocalBuildRun) exec(ctx context.Context) error {
	m, err := manifest.Load(c.targetManifest)
	if err != nil {
		return errors.Annotate(err, "when loading manifest").Tag(isCLIError).Err()
	}

	labels := docker.Labels{
		Created:   clock.Now(ctx).UTC(),
		BuildTool: userAgent,
		BuildMode: "local",
		Extra:     c.labels,
	}

	return stage(ctx, m, func(out *fileset.Set) error {
		logging.Infof(ctx, "Sending tarball with %d files to the docker...", out.Len())

		r, w := io.Pipe()

		var ctxDigest string // sha256 of the context.tar.gz, FYI
		var tarErr error     // error when writing the tarball

		// Feed the tarball to the docker daemon.
		done := make(chan struct{})
		go func() {
			defer close(done)
			ctxDigest, tarErr = sendAsTarball(out, w)
		}()

		imageDigest, dockerErr := docker.Build(ctx, r, append([]string{
			"--no-cache",
			"--tag", m.Name, // attach a local tag for convenience
		}, labels.AsBuildArgs()...))
		r.Close()
		<-done

		switch {
		case dockerErr != nil:
			return errors.Annotate(dockerErr, "failed to build the image").Err()
		case tarErr != nil:
			return errors.Annotate(tarErr, "building the image").Err()
		}

		// TODO(vadimsh): Add -json-output support.
		logging.Infof(ctx, "Context:  %s", ctxDigest)
		logging.Infof(ctx, "Image ID: %s", imageDigest)
		return nil
	})
}

func sendAsTarball(out *fileset.Set, w io.WriteCloser) (digest string, err error) {
	h := sha256.New()
	if err := out.ToTarGz(io.MultiWriter(w, h)); err != nil {
		w.Close()
		return "", errors.Annotate(err, "failed to write the tarball").Err()
	}
	if err := w.Close(); err != nil {
		return "", errors.Annotate(err, "failed to close the write end of the pipe").Err()
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
