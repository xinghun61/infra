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
	"go.chromium.org/luci/common/sync/parallel"

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

// Analyze processes one Analyze request to Tricium.
//
// Launches a workflow customized to the project and listed paths. The run ID
// in the response can be used to track the progress and results of the request
// via the Tricium UI.
func (r *TriciumServer) Analyze(c context.Context, req *tricium.AnalyzeRequest) (*tricium.AnalyzeResponse, error) {
	if err := validateAnalyzeRequest(c, req); err != nil {
		return nil, err
	}
	logging.Infof(c, "[frontend] Analyze request received and validated.")
	runID, code, err := analyzeWithAuth(c, req, config.LuciConfigServer)
	if err != nil {
		return nil, grpc.Errorf(code, "analyze request failed: %v", err)
	}
	logging.Fields{
		"run ID": runID,
	}.Infof(c, "[frontend] Analyze request processed without error.")
	return &tricium.AnalyzeResponse{RunId: runID}, nil
}

// validateAnalyzeRequest returns nil if the request was valid,
// or a grpc error with a reaosn if the request is invalid.
func validateAnalyzeRequest(c context.Context, req *tricium.AnalyzeRequest) error {
	if req.Project == "" {
		return grpc.Errorf(codes.InvalidArgument, "missing project")
	}
	if len(req.Files) == 0 {
		return grpc.Errorf(codes.InvalidArgument, "missing paths")
	}
	switch source := req.Source.(type) {
	case *tricium.AnalyzeRequest_GitCommit:
		gc := source.GitCommit
		if gc.Url == "" {
			return grpc.Errorf(codes.InvalidArgument, "missing git repo URL")
		}
		if gc.Ref == "" {
			return grpc.Errorf(codes.InvalidArgument, "missing git ref")
		}
	case *tricium.AnalyzeRequest_GerritRevision:
		gr := source.GerritRevision
		if gr.Host == "" {
			return grpc.Errorf(codes.InvalidArgument, "missing Gerrit host")
		}
		if gr.Project == "" {
			return grpc.Errorf(codes.InvalidArgument, "missing Gerrit project")
		}
		if gr.Change == "" {
			return grpc.Errorf(codes.InvalidArgument, "missing Gerrit change ID")
		}
		if match, _ := regexp.MatchString(".+~.+~I[0-9a-fA-F]{40}.*", gr.Change); !match {
			return grpc.Errorf(codes.InvalidArgument, "invalid Gerrit change ID: "+gr.Change)
		}
		if gr.GitUrl == "" {
			return grpc.Errorf(codes.InvalidArgument, "missing git repo URL for Gerrit change")
		}
		if gr.GitRef == "" {
			return grpc.Errorf(codes.InvalidArgument, "missing Gerrit revision git ref")
		}
	case nil:
		return grpc.Errorf(codes.InvalidArgument, "missing source")
	default:
		return grpc.Errorf(codes.InvalidArgument, "unexpected source type")
	}
	return nil
}

// analyzeWithAuth wraps 'analyze' in an auth check.
//
// This wrapper is used by the Analyze RPC call and the unwrapped method is
// used by requests coming in via the internal analyze queue.
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
	// Construct the track.AnalyzeRequest entity.
	pc, err := cp.GetProjectConfig(c, req.Project)
	if err != nil {
		return "", fmt.Errorf("failed to get project config: %v", err)
	}
	var paths []string
	for _, file := range req.Files {
		paths = append(paths, file.Path)
	}
	request := &track.AnalyzeRequest{
		Received: clock.Now(c).UTC(),
		Project:  req.Project,
		Paths:    paths,
	}
	repo := tricium.LookupRepoDetails(pc, req)
	if repo == nil {
		return "", fmt.Errorf("failed to find matching repo in project config: %v", req.Project)
	}
	if source := req.GetGerritRevision(); source != nil {
		request.GerritHost = source.Host
		request.GerritProject = source.Project
		request.GerritChange = source.Change
		request.GitURL = source.GitUrl
		request.GitRef = source.GitRef
		request.GerritReportingDisabled = repo.DisableReporting
	} else if source := req.GetGitCommit(); source != nil {
		request.GitURL = source.Url
		request.GitRef = source.Ref
	} else {
		return "", fmt.Errorf("unsupported request source")
	}

	// TODO(qyearsley): Verify that there is no current run for this request,
	// maybe by storing a mapping of hashed requests to run IDs, and checking
	// that nothing exists for this exact request yet.
	//
	// One way to do this would be to make the run ID the hash of the
	// track.AnalyzeRequest; then we would calculate the hash, check if the
	// entity already exists, and if so, abort.

	requestRes := &track.AnalyzeRequestResult{
		ID:    1,
		State: tricium.State_PENDING,
	}
	// TODO(diegomtzg): Consider changing variable names to reflect
	// the difference between track.AnalyzeRequest and tricium.AnalyzeRequest
	lr := &admin.LaunchRequest{
		Project: req.Project,
		Files:   req.Files,
		GitUrl:  request.GitURL,
		GitRef:  request.GitRef,
	}

	// This is a cross-group transaction because first AnalyzeRequest is
	// stored to get the ID, and then AnalyzeRequestResult is stored, with
	// the previously added AnalyzeRequest entity as parent.
	err = ds.RunInTransaction(c, func(c context.Context) (err error) {
		// Add request entity to get ID.
		if err := ds.Put(c, request); err != nil {
			return fmt.Errorf("failed to store AnalyzeRequest entity: %v", err)
		}
		// We can do a few things in parallel when starting an analyze request.
		return parallel.FanOutIn(func(taskC chan<- func() error) {

			// Add AnalyzeRequestResult entity for request status tracking.
			taskC <- func() error {
				requestRes.Parent = ds.KeyForObj(c, request)
				if err := ds.Put(c, requestRes); err != nil {
					return fmt.Errorf("failed to store AnalyzeRequestResult entity: %v", err)
				}
				return nil
			}

			// Launch workflow, enqueue launch request.
			taskC <- func() error {
				lr.RunId = request.ID
				t := tq.NewPOSTTask("/launcher/internal/launch", nil)
				b, err := proto.Marshal(lr)
				if err != nil {
					return fmt.Errorf("failed to enqueue launch request: %v", err)
				}
				t.Payload = b
				return tq.Add(c, common.LauncherQueue, t)
			}

			// Map Gerrit change ID to run ID.
			taskC <- func() error {
				// Nothing to do if there isn't a Gerrit consumer.
				if req.GetGerritRevision() == nil {
					return nil
				}
				g := &GerritChangeToRunID{
					ID:    gerritMappingID(request.GerritHost, request.GerritProject, request.GerritChange, request.GitRef),
					RunID: request.ID,
				}
				if err := ds.Put(c, g); err != nil {
					return fmt.Errorf("failed to store GerritChangeIDtoRunID entity: %v", err)
				}
				return nil
			}
		})
	}, &ds.TransactionOptions{XG: true})
	if err != nil {
		return "", fmt.Errorf("failed to track and launch request: %v", err)
	}
	// Monitor analyze requests per project.
	analyzeRequestCount.Add(c, 1, request.Project)
	return strconv.FormatInt(request.ID, 10), nil
}
