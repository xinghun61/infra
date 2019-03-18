// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"sync"

	"github.com/golang/protobuf/proto"
	"google.golang.org/genproto/protobuf/field_mask"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"go.chromium.org/luci/buildbucket"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/milo"
	"go.chromium.org/luci/logdog/common/types"
	"go.chromium.org/luci/lucictx"
)

// buildUpdater implements an annotee callback for updated annotations
// and makes buildbucket.v2.Builds.UpdateBuild RPCs accordingly.
type buildUpdater struct {
	annAddr    *types.StreamAddr
	buildID    int64
	buildToken string
	client     buildbucketpb.BuildsClient

	// annotations contains latest state of the build in the form of
	// binary serialized milo.Step.
	// Must not be closed.
	annotations chan []byte
}

// Run calls client.UpdateBuild on new b.annotations.
// Logs transient errors and returns a fatal error, if any.
// Stops when done is closed or ctx is done.
func (b *buildUpdater) Run(ctx context.Context, done <-chan struct{}) error {
	cond := sync.NewCond(&sync.Mutex{})
	// protected by cond.L
	var state struct {
		latest    []byte
		latestVer int
		done      bool
	}

	// Listen to new requests.
	go func() {
		locked := func(f func()) {
			cond.L.Lock()
			f()
			cond.L.Unlock()
			cond.Signal()
		}

		for {
			select {
			case ann := <-b.annotations:
				locked(func() {
					state.latest = ann
					state.latestVer++
				})

			case <-ctx.Done():
				locked(func() { state.done = true })
			case <-done:
				locked(func() { state.done = true })
			}
		}
	}()

	// Send requests.
	var sentVer int
	for {
		// Wait for news.
		cond.L.Lock()
		if sentVer == state.latestVer && !state.done {
			cond.Wait()
		}
		local := state
		cond.L.Unlock()

		var err error
		if sentVer != local.latestVer {
			err = b.updateBuildBytes(ctx, local.latest)
			switch status.Code(errors.Unwrap(err)) {
			case codes.OK:
				sentVer = local.latestVer

			case codes.InvalidArgument:
				// This is fatal.
				return err

			default:
				// Hope another future request will succeed.
				// There is another final UpdateBuild call anyway.
				logging.Errorf(ctx, "failed to update build: %s", err)
			}
		}

		if local.done {
			return err
		}
	}
}

// updateBuildBytes is a version of updateBuild that accepts raw annotation
// bytes.
func (b *buildUpdater) updateBuildBytes(ctx context.Context, annBytes []byte) error {
	ann := &milo.Step{}
	if err := proto.Unmarshal(annBytes, ann); err != nil {
		return errors.Annotate(err, "failed to parse annotation proto").Err()
	}
	req, err := b.ParseAnnotations(ctx, ann)
	if err != nil {
		return errors.Annotate(err, "failed to parse UpdateBuild request").Err()
	}
	return b.UpdateBuild(ctx, req)
}

// UpdateBuild updates a build on the buildbucket server.
// Includes a build token in the request.
func (b *buildUpdater) UpdateBuild(ctx context.Context, req *buildbucketpb.UpdateBuildRequest) error {
	ctx = metadata.NewOutgoingContext(ctx, metadata.Pairs(buildbucket.BuildTokenHeader, b.buildToken))
	_, err := b.client.UpdateBuild(ctx, req)
	return err
}

// ParseAnnotations converts an annotation proto to a UpdateBuildRequest that
// updates steps and output properties.
func (b *buildUpdater) ParseAnnotations(ctx context.Context, ann *milo.Step) (*buildbucketpb.UpdateBuildRequest, error) {
	steps, err := buildbucket.ConvertBuildSteps(ctx, ann.Substep, b.annAddr)
	if err != nil {
		return nil, errors.Annotate(err, "failed to parse steps from an annotation proto").Err()
	}

	props, err := milo.ExtractProperties(ann)
	if err != nil {
		return nil, errors.Annotate(err, "failed to extract properties from an annotation proto").Err()
	}

	delete(props.Fields, "buildbucket")
	delete(props.Fields, "$recipe_engine/buildbucket")

	return &buildbucketpb.UpdateBuildRequest{
		Build: &buildbucketpb.Build{
			Id:    b.buildID,
			Steps: steps,
			Output: &buildbucketpb.Build_Output{
				Properties: props,
			},
		},
		UpdateMask: &field_mask.FieldMask{
			Paths: []string{
				"build.steps",
				"build.output.properties",
			},
		},
	}, nil
}

// AnnotationUpdated is an annotee.Options.AnnotationUpdated callback
// that enqueues an UpdateBuild RPC.
// Assumes annBytes will stay unchanged.
func (b *buildUpdater) AnnotationUpdated(annBytes []byte) {
	b.annotations <- annBytes
}

// readBuildSecrets populates c.buildSecrets from swarming secret bytes, if any.
func readBuildSecrets(ctx context.Context) (*buildbucketpb.BuildSecrets, error) {
	swarming := lucictx.GetSwarming(ctx)
	if swarming == nil {
		return nil, nil
	}

	secrets := &buildbucketpb.BuildSecrets{}
	if err := proto.Unmarshal(swarming.SecretBytes, secrets); err != nil {
		return nil, err
	}
	return secrets, nil
}
