// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"errors"
	"strconv"

	"github.com/google/go-querystring/query"
	ds "github.com/luci/gae/service/datastore"
	tq "github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
	"infra/tricium/appengine/common/track"
)

// TriciumServer represents the Tricium pRPC server.
type TriciumServer struct{}

// Server instance to use within this module/package.
var triciumServer = &TriciumServer{}

// Analyze processes one analysis request to Tricium.
//
// Launched a workflow customized to the project and listed paths.  The run ID
// in the response can be used to track the progress and results of the request
// via the Tricium UI.
func (r *TriciumServer) Analyze(c context.Context, req *tricium.TriciumRequest) (*tricium.TriciumResponse, error) {

	if req.Project == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing project")
	}
	if req.GitRef == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing git ref")
	}
	if len(req.Paths) == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing paths to analyze")
	}

	// TODO(emso): Verify that the project in the request is known.
	// TODO(emso): Verify that the user making the request has permission.
	// TODO(emso): Verify that there is no current run for this request (map hashed requests to run IDs).
	// TODO(emso): Read Git repo info from the configuration projects/ endpoint.
	repo := "https://chromium-review.googlesource.com/playground/gerrit-tricium"
	run := &track.Run{
		Received: clock.Now(c).UTC(),
		State:    track.Pending,
	}
	sr := &track.ServiceRequest{
		Project: req.Project,
		Paths:   req.Paths,
		GitRepo: repo,
		GitRef:  req.GitRef,
	}
	rl := pipeline.LaunchRequest{
		Project: sr.Project,
		Paths:   sr.Paths,
		GitRepo: repo,
		GitRef:  sr.GitRef,
	}
	err := ds.RunInTransaction(c, func(c context.Context) error {
		// Add tracking entries for run and request.
		if err := ds.Put(c, run); err != nil {
			return err
		}
		sr.Parent = ds.KeyForObj(c, run)
		if err := ds.Put(c, sr); err != nil {
			return err
		}
		// Launch workflow, enqueue launch request.
		rl.RunID = run.ID
		v, err := query.Values(rl)
		if err != nil {
			return errors.New("failed to encode launch request")
		}
		t := tq.NewPOSTTask("/launcher/internal/queue", v)
		return tq.Add(c, common.LauncherQueue, t)
	}, nil)
	if err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to track and launch request: %v", err)
	}
	logging.Infof(c, "[frontend] Run ID: %s, key: %s", run.ID, ds.KeyForObj(c, run))
	return &tricium.TriciumResponse{
		RunId: strconv.FormatInt(run.ID, 10),
	}, nil
}
