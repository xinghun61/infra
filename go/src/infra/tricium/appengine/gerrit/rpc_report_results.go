// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"fmt"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/track"
)

// ReportResults processes one report results request.
func (r *gerritReporter) ReportResults(c context.Context, req *admin.ReportResultsRequest) (*admin.ReportResultsResponse, error) {
	logging.Debugf(c, "[gerrit-reporter] ReportResults request (run ID: %d)", req.RunId)
	if req.RunId == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	if err := reportResults(c, req, GerritServer); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to report results to Gerrit: %v", err)
	}
	return &admin.ReportResultsResponse{}, nil
}

func reportResults(c context.Context, req *admin.ReportResultsRequest, gerrit API) error {
	request := &track.AnalyzeRequest{ID: req.RunId}
	var comments []*track.Comment
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
		// Get comments.
		func() error {
			requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
			runKey := ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
			analyzerKey := ds.NewKey(c, "AnalyzerRun", req.Analyzer, 0, runKey)
			var comms []*track.Comment
			if err := ds.GetAll(c, ds.NewQuery("Comment").Ancestor(analyzerKey), &comms); err != nil {
				return fmt.Errorf("failed to retrieve comments: %v", err)
			}
			// Only include selected comments.
			for _, comment := range comms {
				commentKey := ds.KeyForObj(c, comment)
				cr := &track.CommentSelection{ID: 1, Parent: commentKey}
				if err := ds.Get(c, cr); err != nil {
					return fmt.Errorf("failed to get CommentSelection: %v", err)
				}
				if cr.Included {
					comments = append(comments, comment)
				}
			}
			return nil
		},
	}
	if err := common.RunInParallel(ops); err != nil {
		return err
	}
	return gerrit.PostRobotComments(c, request.GerritHost, request.GerritChange, request.GerritRevision, req.RunId, comments)
}
