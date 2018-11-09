// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"sync"

	"google.golang.org/genproto/protobuf/field_mask"

	"go.chromium.org/luci/buildbucket"
	"go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/milo"
	"go.chromium.org/luci/logdog/common/types"
)

// runBuildUpdater calls client.UpdateBuild.
// Assumes requests are not mutated.
// Assumes references in the channel are unique.
// Assumes latest request overrides preceding ones.
// Exits when requests is closed.
// Logs transient errors and returns a fatal error, if any.
func runBuildUpdater(ctx context.Context, client buildbucketpb.BuildsClient, requests <-chan *buildbucketpb.UpdateBuildRequest) error {
	var latest *buildbucketpb.UpdateBuildRequest
	done := false
	cond := sync.NewCond(&sync.Mutex{})

	// Listen to new requests.
	go func() {
		for r := range requests {
			cond.L.Lock()
			latest = r
			cond.L.Unlock()
			cond.Signal()
		}

		cond.L.Lock()
		done = true
		cond.L.Unlock()
		cond.Signal()
	}()

	// Send requests.
	var sent *buildbucketpb.UpdateBuildRequest
	for {
		// Wait for news.
		cond.L.Lock()
		if sent == latest && !done {
			cond.Wait()
		}
		localLatest := latest
		localDone := done
		cond.L.Unlock()

		var err error
		if sent != localLatest {
			_, err = client.UpdateBuild(ctx, localLatest)
			if err != nil {
				logging.Errorf(ctx, "UpdateBuild RPC failed: %s", err)
			} else {
				sent = localLatest
			}
		}

		if localDone {
			return err
		}
	}
}

// parseUpdateBuildRequest converts an annotation proto to an UpdateBuild RPC
// request.
// The returned request only attempts to update steps and output properties
// and asks no build fields in response.
// The context is used only for logging.
// annAddr is used to construct absolute logdog URLs of step logs.
func parseUpdateBuildRequest(c context.Context, ann *milo.Step, annAddr *types.StreamAddr) (*buildbucketpb.UpdateBuildRequest, error) {
	steps, err := buildbucket.ConvertBuildSteps(c, ann.Substep, annAddr)
	if err != nil {
		return nil, errors.Annotate(err, "failed to parse steps from an annotation proto").Err()
	}

	props, err := milo.ExtractProperties(ann)
	if err != nil {
		return nil, errors.Annotate(err, "failed to extract properties from an annotation proto").Err()
	}

	return &buildbucketpb.UpdateBuildRequest{
		Build: &buildbucketpb.Build{
			Steps: steps,
			Output: &buildbucketpb.Build_Output{
				Properties: props,
			},
		},
		UpdateMask: &field_mask.FieldMask{
			Paths: []string{
				"steps",
				"output.properties",
			},
		},
		// minimize output by asking nothing back.
		Fields: &field_mask.FieldMask{},
	}, nil
}
