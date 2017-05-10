// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"strconv"

	"github.com/golang/protobuf/proto"
	ds "github.com/luci/gae/service/datastore"
	tq "github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
	"infra/tricium/appengine/common/track"
)

// TriciumServer represents the Tricium pRPC server.
type TriciumServer struct{}

// Server instance to use within this module/package.
var server = &TriciumServer{}

const repo = "https://chromium-review.googlesource.com/playground/gerrit-tricium"

// Analyze processes one analysis request to Tricium.
//
// Launched a workflow customized to the project and listed paths.  The run ID
// in the response can be used to track the progress and results of the request
// via the Tricium UI.
func (r *TriciumServer) Analyze(c context.Context, req *tricium.AnalyzeRequest) (*tricium.AnalyzeResponse, error) {
	if req.Project == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing project")
	}
	if req.GitRef == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing git ref")
	}
	if len(req.Paths) == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing paths to analyze")
	}
	runID, code, err := analyze(c, req, config.LuciConfigServer)
	if err != nil {
		logging.WithError(err).Errorf(c, "analyze failed: %v", err)
		return nil, grpc.Errorf(code, "failed to execute analyze request")
	}
	logging.Infof(c, "[frontend] Run ID: %s", runID)
	return &tricium.AnalyzeResponse{runID}, nil
}

func analyze(c context.Context, req *tricium.AnalyzeRequest, cp config.ProviderAPI) (string, codes.Code, error) {
	pc, err := cp.GetProjectConfig(c, req.Project)
	if err != nil {
		return "", codes.Internal, fmt.Errorf("failed to get project config, project: %q: %v", req.Project, err)
	}
	ok, err := tricium.CanRequest(c, pc)
	if err != nil {
		return "", codes.Internal, fmt.Errorf("failed to authorize: %v", err)
	}
	if !ok {
		return "", codes.PermissionDenied, fmt.Errorf("no request access for project %q", req.Project)
	}
	// TODO(emso): Verify that there is no current run for this request (map hashed requests to run IDs).
	// TODO(emso): Read Git repo info from the configuration projects/ endpoint.
	// TODO(emso): Verify that a project has Gerrit details if a Gerrit reporter has been selected.
	run := &track.Run{
		Received: clock.Now(c).UTC(),
		State:    tricium.State_PENDING,
		Project:  req.Project,
		Reporter: req.Reporter,
	}
	sr := &track.ServiceRequest{
		Project: req.Project,
		Paths:   req.Paths,
		GitRepo: repo,
		GitRef:  req.GitRef,
	}
	lr := &admin.LaunchRequest{
		Project: sr.Project,
		Paths:   sr.Paths,
		GitRepo: repo,
		GitRef:  sr.GitRef,
	}
	// This is a cross-group transaction because first Run is stored to get the ID,
	// and then ServiceRequest is stored, with Run key as parent.
	err = ds.RunInTransaction(c, func(c context.Context) (err error) {
		// Add tracking entries for run.
		if err := ds.Put(c, run); err != nil {
			return fmt.Errorf("failed to store run entry: %v", err)
		}
		// Run the below operations in parallel.
		done := make(chan error)
		defer func() {
			if err2 := <-done; err == nil {
				err = err2
			}
		}()
		go func() {
			// Add tracking entry for service request.
			sr.Parent = ds.KeyForObj(c, run)
			if err := ds.Put(c, sr); err != nil {
				done <- fmt.Errorf("failed to store service request: %v", err)
				return
			}
			done <- nil
		}()
		// Launch workflow, enqueue launch request.
		lr.RunId = run.ID
		t := tq.NewPOSTTask("/launcher/internal/launch", nil)
		b, err := proto.Marshal(lr)
		if err != nil {
			return fmt.Errorf("failed to enqueue launch request: %v", err)
		}
		t.Payload = b
		return tq.Add(c, common.LauncherQueue, t)
	}, &ds.TransactionOptions{XG: true})
	if err != nil {
		return "", codes.Internal, fmt.Errorf("failed to track and launch request: %v", err)
	}
	return strconv.FormatInt(run.ID, 10), codes.OK, nil
}
