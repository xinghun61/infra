// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package cloudbuild wraps interaction with Google Cloud Build.
package cloudbuild

import (
	"context"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"

	"golang.org/x/oauth2"
	"google.golang.org/api/cloudbuild/v1"
	"google.golang.org/api/option"

	"go.chromium.org/luci/common/errors"

	"infra/cmd/cloudbuildhelper/docker"
	"infra/cmd/cloudbuildhelper/manifest"
	"infra/cmd/cloudbuildhelper/storage"
)

// Builder knows how to trigger Cloud Build builds and check their status.
type Builder struct {
	builds *cloudbuild.ProjectsBuildsService
	cfg    manifest.CloudBuildConfig
}

// Request specifies what we want to build and push.
//
// It is passed to Trigger.
type Request struct {
	// Source is a reference to the uploaded tarball with the context directory.
	Source *storage.Object

	// Image is a name of the image (perhaps with ":<tag>") to produce and push.
	//
	// Should include a docker registry part, e.g. have form "gcr.io/../...".
	//
	// If empty, Builder will still build an image, but will not push it anywhere.
	// Useful to verify Dockerfile is working without accumulating cruft.
	Image string

	// Labels is a labels to put into the produced docker image (if any).
	Labels docker.Labels
}

// Status is possible status of a Cloud Build.
type Status string

// See https://cloud.google.com/cloud-build/docs/api/reference/rest/Shared.Types/Status
const (
	StatusUnknown       Status = "STATUS_UNKNOWN"
	StatusQueued        Status = "QUEUED"
	StatusWorking       Status = "WORKING"
	StatusSuccess       Status = "SUCCESS"
	StatusFailure       Status = "FAILURE"
	StatusInternalError Status = "INTERNAL_ERROR"
	StatusTimeout       Status = "TIMEOUT"
	StatusCancelled     Status = "CANCELLED"
)

// IsTerminal is true if the build is done (successfully or not).
func (s Status) IsTerminal() bool {
	switch s {
	case StatusSuccess, StatusFailure, StatusInternalError, StatusTimeout, StatusCancelled:
		return true
	default:
		return false
	}
}

// Build represents a pending, in-flight or completed build.
type Build struct {
	// Theses fields are always available.
	ID            string // UUID string with the build ID
	LogURL        string // URL to a UI page (for humans) with build logs
	Status        Status // see the enum
	StatusDetails string // human readable string with more details (if any)

	// These fields are available only for successful builds.
	InputHashes  map[string]string // SHA256 hashes of build inputs ("gs://..." => SHA256)
	OutputImage  string            // uploaded image name (if any)
	OutputDigest string            // digest (in "sha256:..." form) of the image
}

// New prepares a Builder instance.
func New(ctx context.Context, ts oauth2.TokenSource, cfg manifest.CloudBuildConfig) (*Builder, error) {
	svc, err := cloudbuild.NewService(ctx, option.WithTokenSource(ts))
	if err != nil {
		return nil, errors.Annotate(err, "failed to instantiate cloudbuild.Service").Err()
	}
	return &Builder{
		builds: cloudbuild.NewProjectsBuildsService(svc),
		cfg:    cfg,
	}, nil
}

// Trigger launches a new build, returning its details.
//
// ID of the returned build can be used to query its status later in Check(...).
func (b *Builder) Trigger(ctx context.Context, r Request) (*Build, error) {
	var pushImages []string
	dockerArgs := append([]string{
		"build",
		".",
		"--network", "cloudbuild", // this is what "gcloud build submit" uses, it is documented
		"--no-cache", // state of the cache on Cloud Build workers is not well defined
	}, r.Labels.AsBuildArgs()...)

	// If asked to push the image, tag it locally and ask Cloud Build to push out
	// this tag to the registry as well.
	if r.Image != "" {
		dockerArgs = append(dockerArgs, "--tag", r.Image)
		pushImages = append(pushImages, r.Image)
	}

	// Version of gcr.io/cloud-builders/docker image to use.
	var dockerVer string
	switch v := b.cfg.Docker; {
	case v == "":
		dockerVer = ":latest"
	case strings.HasPrefix(v, "sha256:"):
		dockerVer = "@" + v
	default:
		dockerVer = ":" + v
	}

	// Note: this call roughly matches what "gcloud build submit --tag ..." does,
	// except we tweak options a bit.
	call := b.builds.Create(b.cfg.Project, &cloudbuild.Build{
		// See https://cloud.google.com/cloud-build/docs/api/reference/rest/Shared.Types/Build#BuildOptions
		Options: &cloudbuild.BuildOptions{
			LogStreamingOption:    "STREAM_ON",
			Logging:               "GCS_ONLY",
			RequestedVerifyOption: "VERIFIED",
			SourceProvenanceHash:  []string{"SHA256"},
		},

		// Where to fetch "." used from the build step below.
		Source: &cloudbuild.Source{
			StorageSource: &cloudbuild.StorageSource{
				Bucket:     r.Source.Bucket,
				Object:     r.Source.Name,
				Generation: r.Source.Generation,
			},
		},

		// Build "." and tag it locally (on the worker).
		Steps: []*cloudbuild.BuildStep{
			{
				Name: "gcr.io/cloud-builders/docker" + dockerVer,
				Args: dockerArgs,
			},
		},

		// Push whatever we tagged (if anything) to the registry.
		Images: pushImages,
	})

	op, err := call.Context(ctx).Do()
	if err != nil {
		return nil, errors.Annotate(err, "API call to Cloud Build failed").Err()
	}

	// Cloud Build returns triggered build details with operation's metadata.
	var metadata struct {
		Build *cloudbuild.Build `json:"build"`
	}
	if err := json.Unmarshal(op.Metadata, &metadata); err != nil {
		return nil, errors.Annotate(err, "failed to unmarshal operations metadata %s", op.Metadata).Err()
	}
	if metadata.Build == nil {
		return nil, errors.Reason("`build` field unexpectedly missing in the metadata %s", op.Metadata).Err()
	}

	return makeBuild(metadata.Build), nil
}

// Check returns details of a build given its ID.
func (b *Builder) Check(ctx context.Context, bid string) (*Build, error) {
	build, err := b.builds.Get(b.cfg.Project, bid).Context(ctx).Do()
	if err != nil {
		return nil, errors.Annotate(err, "API call to Cloud Build failed").Err()
	}
	return makeBuild(build), nil
}

func makeBuild(b *cloudbuild.Build) *Build {
	// Parse SourceProvenance into more digestible "file => SHA256" map.
	var prov map[string]string
	if b.SourceProvenance != nil {
		prov = make(map[string]string, len(b.SourceProvenance.FileHashes))
		for name, hashes := range b.SourceProvenance.FileHashes {
			digest := "<unknown>"
			for _, h := range hashes.FileHash {
				if h.Type == "SHA256" {
					digest = b64ToHex(h.Value)
					break
				}
			}
			prov[name] = digest
		}
	}

	// Grab the image from the result. There should be at most one.
	var outImg, outDigest string
	if b.Results != nil {
		for _, img := range b.Results.Images {
			outImg = img.Name
			outDigest = img.Digest
			break
		}
	}

	return &Build{
		ID:            b.Id,
		LogURL:        b.LogUrl,
		Status:        Status(b.Status),
		StatusDetails: b.StatusDetail,
		InputHashes:   prov,
		OutputImage:   outImg,
		OutputDigest:  outDigest,
	}
}

func b64ToHex(b string) string {
	blob, err := base64.StdEncoding.DecodeString(b)
	if err != nil {
		return fmt.Sprintf("<bad hash %s>", err) // should not be happening
	}
	return hex.EncodeToString(blob)
}
