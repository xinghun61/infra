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
	"infra/tricium/appengine/common/track"
)

// GerritReporter represents the internal Tricium pRPC Gerrit reporter server.
type gerritReporter struct{}

var server = &gerritReporter{}

// ReportLaunched processes one report launched request.
func (r *gerritReporter) ReportLaunched(c context.Context, req *admin.ReportLaunchedRequest) (*admin.ReportLaunchedResponse, error) {
	logging.Debugf(c, "[gerrit-reporter] ReportLaunched request (run ID: %d)", req.RunId)
	if req.RunId == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	if err := reportLaunched(c, req, GerritServer); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to report launched to Gerrit: %v", err)
	}
	return &admin.ReportLaunchedResponse{}, nil
}

func reportLaunched(c context.Context, req *admin.ReportLaunchedRequest, gerrit API) error {
	// The Git repo and ref in the service request should correspond to the Gerrit
	// repo for the project. This request is typically done by the Gerrit poller.
	request := &track.AnalyzeRequest{ID: req.RunId}
	if err := ds.Get(c, request); err != nil {
		return fmt.Errorf("failed to get AnalyzeRequest entity (ID: %s): %v", req.RunId, err)
	}
	msg := fmt.Sprintf("Tricium is analyzing the last uploaded patch set (run ID: %s)", req.RunId)
	return gerrit.PostReviewMessage(c, request.GitRepo, request.GerritChange, request.GerritRevision, msg)
}
