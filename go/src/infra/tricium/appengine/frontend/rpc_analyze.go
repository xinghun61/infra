// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"regexp"
	"strconv"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"

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
// Launches a workflow customized to the project and listed paths. The run ID
// in the response can be used to track the progress and results of the request
// via the Tricium UI.
func (r *TriciumServer) Analyze(c context.Context, req *tricium.AnalyzeRequest) (*tricium.AnalyzeResponse, error) {
	if err := validateAnalyzeRequest(c, req); err != nil {
		return nil, err
	}
	runID, code, err := analyzeWithAuth(c, req, config.LuciConfigServer)
	if err != nil {
		logging.WithError(err).Errorf(c, "analyze failed: %v", err)
		return nil, grpc.Errorf(code, "failed to execute analyze request")
	}
	logging.Infof(c, "[frontend] Run ID: %s", runID)
	return &tricium.AnalyzeResponse{RunId: runID}, nil
}

func validateAnalyzeRequest(c context.Context, req *tricium.AnalyzeRequest) error {
	if req.Project == "" {
		msg := "missing 'project' field in Analyze request"
		logging.Errorf(c, msg)
		return grpc.Errorf(codes.InvalidArgument, msg)
	}
	if len(req.Paths) == 0 {
		msg := "missing 'paths' field in Analyze request"
		logging.Errorf(c, msg)
		return grpc.Errorf(codes.InvalidArgument, msg)
	}
	if req.Consumer == tricium.Consumer_GERRIT {
		gd := req.GetGerritDetails()
		if gd == nil {
			msg := "missing 'gerrit_details' field"
			logging.Errorf(c, msg)
			return grpc.Errorf(codes.InvalidArgument, msg)
		}
		if gd.Project == "" {
			msg := "missing 'project' field in GerritConsumerDetails message"
			logging.Errorf(c, msg)
			return grpc.Errorf(codes.InvalidArgument, msg)
		}
		if gd.Change == "" {
			msg := "missing 'change' field in GerritConsumerDetails message"
			logging.Errorf(c, msg)
			return grpc.Errorf(codes.InvalidArgument, msg)
		}
		if match, _ := regexp.MatchString(".+~.+~I[0-9a-fA-F]{40}.*", gd.Change); !match {
			msg := fmt.Sprintf("'change' value '%s' in GerritConsumerDetails message doesn't match expected format", gd.Change)
			logging.Errorf(c, msg)
			return grpc.Errorf(codes.InvalidArgument, msg)
		}
		if gd.Revision == "" {
			msg := "missing 'revision' field in GerritConsumerDetails message"
			logging.Errorf(c, msg)
			return grpc.Errorf(codes.InvalidArgument, msg)
		}
	}
	return nil
}

// analyzeWithAuth wraps 'analyze' in an auth check.
//
// This wrapper is used by the Analyze RPC call and the unwrapped method is used
// by requests coming in via the internal analyze queue.
func analyzeWithAuth(c context.Context, req *tricium.AnalyzeRequest, cp config.ProviderAPI) (string, codes.Code, error) {
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
	runID, err := analyze(c, req, cp)
	if err != nil {
		return runID, codes.Internal, err
	}
	return runID, codes.OK, nil
}

func analyze(c context.Context, req *tricium.AnalyzeRequest, cp config.ProviderAPI) (string, error) {
	// TODO(emso): Verify that there is no current run for this request (map hashed requests to run IDs).
	sc, err := cp.GetServiceConfig(c)
	if err != nil {
		return "", fmt.Errorf("failed to get service config: %v", err)
	}
	request := &track.AnalyzeRequest{
		Received: clock.Now(c).UTC(),
		Project:  req.Project,
		Paths:    req.Paths,
		GitRef:   req.GitRef,
		Consumer: req.Consumer,
	}
	pd := tricium.LookupProjectDetails(sc, req.Project)
	if pd == nil {
		return "", fmt.Errorf("failed to lookup project details, project: %s", req.Project)
	}
	if pd.RepoDetails.Kind == tricium.RepoDetails_GIT {
		rd := pd.RepoDetails.GitDetails
		request.GitRepo = rd.Repository
		if request.GitRef == "" {
			request.GitRef = rd.Ref
		}
	} else {
		return "", fmt.Errorf("unsupported repository kind in project details: %s", pd.RepoDetails.Kind)
	}
	if req.Consumer == tricium.Consumer_GERRIT {
		gd := pd.GetGerritDetails()
		if gd == nil {
			return "", fmt.Errorf("missing Gerrit details for project, project: %s", req.Project)
		}
		request.GerritHost = gd.Host
		request.GerritChange = req.GerritDetails.Change
		request.GerritRevision = req.GerritDetails.Revision
	}
	requestRes := &track.AnalyzeRequestResult{
		ID:    1,
		State: tricium.State_PENDING,
	}
	lr := &admin.LaunchRequest{
		Project: request.Project,
		Paths:   request.Paths,
		GitRepo: request.GitRepo,
		GitRef:  request.GitRef,
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
			// Add AnalyzeRequestResult entity for request status tracking.
			func() error {
				requestRes.Parent = ds.KeyForObj(c, request)
				if err := ds.Put(c, requestRes); err != nil {
					return fmt.Errorf("failed to store AnalyzeRequestResult entity: %v", err)
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
			// Map Gerrit change ID to run ID.
			func() error {
				// Nothing to do if there isn't a Gerrit consumer.
				if req.Consumer != tricium.Consumer_GERRIT {
					return nil
				}
				g := &GerritChangeToRunID{
					ID:    gerritMappingID(request.Project, request.GerritChange),
					RunID: request.ID,
				}
				if err := ds.Put(c, g); err != nil {
					return fmt.Errorf("failed to store GerritChangeIDtoRunID entity: %v", err)
				}
				return nil
			},
		}
		return common.RunInParallel(ops)
	}, &ds.TransactionOptions{XG: true})
	if err != nil {
		return "", fmt.Errorf("failed to track and launch request: %v", err)
	}
	// Monitor analyze requests per project,
	analyzeRequestCount.Add(c, 1, request.Project)
	return strconv.FormatInt(request.ID, 10), nil
}
