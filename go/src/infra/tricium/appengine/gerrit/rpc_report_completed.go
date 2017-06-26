// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"bytes"
	"fmt"

	ds "github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/track"
)

// ReportCompleted implements the admin.Reporter interface.
func (r *gerritReporter) ReportCompleted(c context.Context, req *admin.ReportCompletedRequest) (*admin.ReportCompletedResponse, error) {
	logging.Debugf(c, "[gerrit-reporter] ReportCompleted request (run ID: %d)", req.RunId)
	if req.RunId == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	if err := reportCompleted(c, req, GerritServer); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to report completed to Gerrit: %v", err)
	}
	return &admin.ReportCompletedResponse{}, nil
}

func reportCompleted(c context.Context, req *admin.ReportCompletedRequest, gerrit API) error {
	request := &track.AnalyzeRequest{ID: req.RunId}
	var analyzerResults []*track.AnalyzerRunResult
	ops := []func() error{
		// Get Git details.
		func() error {
			// The Git repo and ref in the service request should correspond to the Gerrit
			// repo for the project. This request is typically done by the Gerrit poller.
			if err := ds.Get(c, request); err != nil {
				return fmt.Errorf("failed to get AnalyzeRequest entity (ID: %s): %v", req.RunId, err)
			}
			return nil
		},
		// Get analyzer results.
		func() error {
			requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
			runKey := ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
			if err := ds.GetAll(c, ds.NewQuery("AnalyzerRunResult").Ancestor(runKey), &analyzerResults); err != nil {
				return fmt.Errorf("failed to get AnalyzerRunResult entities: %v", err)
			}
			return nil
		},
	}
	if err := common.RunInParallel(ops); err != nil {
		return err
	}
	// Create result message.
	n := 0
	var buf bytes.Buffer
	for _, ar := range analyzerResults {
		n += ar.NumComments
		buf.WriteString(fmt.Sprintf("  %s: %d\n", ar.Name, ar.NumComments))
	}
	msg := fmt.Sprintf("Tricium finished analyzing patch set and found %d results (run ID: %d).\n%s", n, req.RunId, buf.String())
	return gerrit.PostReviewMessage(c, request.GitRepo, request.GerritChange, request.GerritRevision, msg)
}
