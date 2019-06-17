// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"context"
	"regexp"
	"strconv"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/grpc/grpcutil"

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

// Regular expression describing a valid change ID (https://goo.gl/U49fRn).
var changeIDPattern = regexp.MustCompile(".+~.+~I[0-9a-fA-F]{40}.*")

// Analyze processes one Analyze request to Tricium.
//
// Launches a workflow customized to the project and listed paths. The run ID
// in the response can be used to track the progress and results of the request
// via the Tricium UI.
func (r *TriciumServer) Analyze(c context.Context, req *tricium.AnalyzeRequest) (res *tricium.AnalyzeResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	if err := validateAnalyzeRequest(c, req); err != nil {
		return nil, err
	}
	runID, err := analyzeWithAuth(c, req, config.LuciConfigServer)
	if err != nil {
		return nil, errors.Annotate(err, "invalid request").
			Tag(grpcutil.InvalidArgumentTag).Err()
	}
	logging.Fields{
		"runID": runID,
	}.Infof(c, "Analyze request processed.")
	return &tricium.AnalyzeResponse{RunId: runID}, nil
}

// validateAnalyzeRequest returns an error if the request is invalid.
//
// The returned error should be tagged for gRPC by the caller.
func validateAnalyzeRequest(c context.Context, req *tricium.AnalyzeRequest) error {
	if req.Project == "" {
		return errors.Reason("missing project").Err()
	}
	if len(req.Files) == 0 {
		return errors.Reason("missing paths").Err()
	}
	switch source := req.Source.(type) {
	case *tricium.AnalyzeRequest_GitCommit:
		gc := source.GitCommit
		if gc.Url == "" {
			return errors.Reason("missing git repo URL").Err()
		}
		if gc.Ref == "" {
			return errors.Reason("missing git ref").Err()
		}
	case *tricium.AnalyzeRequest_GerritRevision:
		gr := source.GerritRevision
		if gr.Host == "" {
			return errors.Reason("missing Gerrit host").Err()
		}
		if gr.Project == "" {
			return errors.Reason("missing Gerrit project").Err()
		}
		if gr.Change == "" {
			return errors.Reason("missing Gerrit change ID").Err()
		}
		if !changeIDPattern.MatchString(gr.Change) {
			return errors.Reason("invalid Gerrit change ID: " + gr.Change).Err()
		}
		if gr.GitUrl == "" {
			return errors.Reason("missing git repo URL for Gerrit change").Err()
		}
		if gr.GitRef == "" {
			return errors.Reason("missing Gerrit revision git ref").Err()
		}
	case nil:
		return errors.Reason("missing source").Err()
	default:
		return errors.Reason("unexpected source type").Err()
	}
	return nil
}

// analyzeWithAuth wraps 'analyze' in an auth check.
//
// This wrapper is used by the Analyze RPC call and the unwrapped method is
// used by requests coming in via the internal analyze queue.
func analyzeWithAuth(c context.Context, req *tricium.AnalyzeRequest, cp config.ProviderAPI) (string, error) {
	pc, err := cp.GetProjectConfig(c, req.Project)
	if err != nil {
		return "", errors.Annotate(err, "failed to get project config %q", req.Project).
			Tag(grpcutil.InternalTag).Err()
	}
	ok, err := tricium.CanRequest(c, pc)
	if err != nil {
		return "", errors.Annotate(err, "failed to authorize").
			Tag(grpcutil.InternalTag).Err()
	}
	if !ok {
		return "", errors.Reason("no request access for project %q", req.Project).
			Tag(grpcutil.PermissionDeniedTag).Err()
	}
	runID, err := analyze(c, req, cp)
	if err != nil {
		return runID, errors.Annotate(err, "failed to analyze").
			Tag(grpcutil.InternalTag).Err()
	}
	return runID, nil
}

func analyze(c context.Context, req *tricium.AnalyzeRequest, cp config.ProviderAPI) (string, error) {
	// Construct the track.AnalyzeRequest entity.
	pc, err := cp.GetProjectConfig(c, req.Project)
	if err != nil {
		return "", errors.Annotate(err, "failed to get project config").Err()
	}
	var paths []string
	var files []tricium.Data_File
	for _, file := range req.Files {
		paths = append(paths, file.Path)
		files = append(files, *file)
	}
	request := &track.AnalyzeRequest{
		Received: clock.Now(c).UTC(),
		Project:  req.Project,
		Files:    files,
	}
	repo := tricium.LookupRepoDetails(pc, req)
	if repo == nil {
		return "", errors.Reason("failed to find matching repo in project config: %v", req.Project).Err()
	}
	if source := req.GetGerritRevision(); source != nil {
		request.GerritHost = source.Host
		request.GerritProject = source.Project
		request.GerritChange = source.Change
		request.GitURL = source.GitUrl
		request.GitRef = source.GitRef
		request.GerritReportingDisabled = repo.DisableReporting
		request.CommitMessage = source.CommitMessage
	} else if source := req.GetGitCommit(); source != nil {
		request.GitURL = source.Url
		request.GitRef = source.Ref
	} else {
		return "", errors.Reason("unsupported request source").Err()
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
	// TODO(qyearsley): Clarify variable names to reflect the difference
	// between track.AnalyzeRequest and tricium.AnalyzeRequest.
	lr := &admin.LaunchRequest{
		Project:       req.Project,
		Files:         req.Files,
		GitUrl:        request.GitURL,
		GitRef:        request.GitRef,
		CommitMessage: request.CommitMessage,
	}

	// This is a cross-group transaction because first AnalyzeRequest is
	// stored to get the ID, and then AnalyzeRequestResult is stored, with
	// the previously added AnalyzeRequest entity as parent.
	err = ds.RunInTransaction(c, func(c context.Context) (err error) {
		// Add request entity to get ID.
		if err := ds.Put(c, request); err != nil {
			return errors.Annotate(err, "failed to store AnalyzeRequest entity").Err()
		}
		// We can do a few things in parallel when starting an analyze request.
		return parallel.FanOutIn(func(taskC chan<- func() error) {

			// Add AnalyzeRequestResult entity for request status tracking.
			taskC <- func() error {
				requestRes.Parent = ds.KeyForObj(c, request)
				if err := ds.Put(c, requestRes); err != nil {
					return errors.Annotate(err, "failed to store AnalyzeRequestResult entity").Err()
				}
				return nil
			}

			// Launch workflow, enqueue launch request.
			taskC <- func() error {
				lr.RunId = request.ID
				t := tq.NewPOSTTask("/launcher/internal/launch", nil)
				b, err := proto.Marshal(lr)
				if err != nil {
					return errors.Annotate(err, "failed to enqueue launch request").Err()
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
					return errors.Annotate(err, "failed to store GerritChangeIDtoRunID entity").Err()
				}
				return nil
			}
		})
	}, &ds.TransactionOptions{XG: true})
	if err != nil {
		return "", errors.Annotate(err, "failed to track and launch request").Err()
	}
	// Monitor analyze requests per project.
	analyzeRequestCount.Add(c, 1, request.Project)
	return strconv.FormatInt(request.ID, 10), nil
}
