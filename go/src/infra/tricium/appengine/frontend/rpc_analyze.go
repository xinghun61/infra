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

// Analyze processes one Analyze request to Tricium.
//
// Launched a workflow customized to the project and listed paths. The run ID
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
	request := &track.AnalyzeRequest{
		Received: clock.Now(c).UTC(),
		Project:  req.Project,
		Reporter: req.Reporter,
		Paths:    req.Paths,
		GitRepo:  repo,
		GitRef:   req.GitRef,
	}
	requestRes := &track.AnalyzeRequestResult{
		ID:    1,
		State: tricium.State_PENDING,
	}
	lr := &admin.LaunchRequest{
		Project: req.Project,
		Paths:   req.Paths,
		GitRepo: repo,
		GitRef:  req.GitRef,
	}

	// This is a cross-group transaction because first AnalyzeRequest is stored to get the ID,
	// and then AnalyzeRequestResult is stored, with the previously added AnalyzeRequest entity as parent.
	err = ds.RunInTransaction(c, func(c context.Context) (err error) {
		// Add request entity to get ID.
		if err := ds.Put(c, request); err != nil {
			return fmt.Errorf("failed to store AnalyzeRequest entity: %v", err)
		}
		// Operations to run in parallel in the below transaction.
		ops := []func() error{
			// Add AnalyzeRequestResult entity for requst status tracking.
			func() error {
				requestRes.Parent = ds.KeyForObj(c, request)
				if err := ds.Put(c, requestRes); err != nil {
					return fmt.Errorf("failed to store AnalyzeRequestResult entry: %v", err)
				}
				return nil
			},
			// Launch workflow, enqueue launch request.
			func() error {
				lr.RunId = request.ID
				t := tq.NewPOSTTask("/launcher/internal/launch", nil)
				b, err := proto.Marshal(lr)
				if err != nil {
					return fmt.Errorf("failed to enqueue launch request: %v", err)
				}
				t.Payload = b
				return tq.Add(c, common.LauncherQueue, t)
			},
		}
		return common.RunInParallel(ops)
	}, &ds.TransactionOptions{XG: true})
	if err != nil {
		return "", codes.Internal, fmt.Errorf("failed to track and launch request: %v", err)
	}
	return strconv.FormatInt(request.ID, 10), codes.OK, nil
}
