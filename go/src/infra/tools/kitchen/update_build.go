// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"sync"

	"github.com/golang/protobuf/proto"
	"google.golang.org/genproto/protobuf/field_mask"
	"google.golang.org/grpc/metadata"

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
func (b *buildUpdater) Run(ctx context.Context) error {
	ctx = metadata.NewOutgoingContext(ctx, metadata.Pairs(buildbucket.BuildTokenHeader, b.buildToken))

	cond := sync.NewCond(&sync.Mutex{})
	// protected by cond.L
	var state struct {
		latest    []byte
		latestVer int
		done      bool
	}

	// Listen to new requests.
	go func() {
		for {
			select {
			case ann := <-b.annotations:
				cond.L.Lock()
				state.latest = ann
				state.latestVer++
				cond.L.Unlock()
				cond.Signal()

			case <-ctx.Done():
				cond.L.Lock()
				state.done = true
				cond.L.Unlock()
				cond.Signal()
				return
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
			if err = b.updateBuildBytes(ctx, local.latest); err != nil {
				logging.Errorf(ctx, "failed to update build: %s", err)
			} else {
				sentVer = local.latestVer
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
	return b.updateBuild(ctx, ann)
}

// updateBuild makes an UpdateBuild RPC based on the annotation,
// see also b.parseRequest.
func (b *buildUpdater) updateBuild(ctx context.Context, ann *milo.Step) error {
	req, err := b.parseRequest(ctx, ann)
	if err != nil {
		return errors.Annotate(err, "failed to parse UpdateBuild request").Err()
	}

	if _, err = b.client.UpdateBuild(ctx, req); err != nil {
		return errors.Annotate(err, "UpdateBuild RPC failed").Err()
	}

	return nil
}

// parseRequest converts a binary-serialized annotation proto to an UpdateBuild
// RPC request.
// The returned request only attempts to update steps and output properties
// and asks no build fields in response.
func (b *buildUpdater) parseRequest(ctx context.Context, ann *milo.Step) (*buildbucketpb.UpdateBuildRequest, error) {
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
		// minimize output by asking nothing back.
		Fields: &field_mask.FieldMask{},
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
