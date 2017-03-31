// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"encoding/json"
	"fmt"
	"strconv"

	ds "github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

// Results processes one results request to Tricium.
func (r *TriciumServer) Results(c context.Context, req *tricium.ResultsRequest) (*tricium.ResultsResponse, error) {
	if req.RunId == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	runID, err := strconv.ParseInt(req.RunId, 10, 64)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to parse run ID: %s", req.RunId)
		return nil, grpc.Errorf(codes.InvalidArgument, "invalid run ID")
	}
	results, isMerged, err := results(c, runID)
	if err != nil {
		logging.WithError(err).Errorf(c, "results failed: %v", err)
		return nil, grpc.Errorf(codes.Internal, "failed to execute results request")
	}
	logging.Infof(c, "[frontend] Results: %v", results)
	return &tricium.ResultsResponse{Results: results, IsMerged: isMerged}, nil
}

func results(c context.Context, runID int64) (*tricium.Data_Results, bool, error) {
	run := &track.Run{ID: runID}
	if err := ds.Get(c, run); err != nil {
		return nil, false, fmt.Errorf("failed to read run entry: %v", err)
	}
	runKey := ds.NewKey(c, "Run", "", runID, nil)
	var comments []*track.ResultComment
	q := ds.NewQuery("ResultComment").Ancestor(runKey)
	if err := ds.GetAll(c, q, &comments); err != nil {
		return nil, false, fmt.Errorf("failed to read result comments: %v", err)
	}
	isMerged := false
	res := &tricium.Data_Results{}
	for _, comment := range comments {
		if comment.Included {
			comm := &tricium.Data_Comment{}
			if err := json.Unmarshal([]byte(comment.Comment), comm); err != nil {
				return nil, false, fmt.Errorf("failed to unmarshal result comment: %v", err)
			}
			res.Comments = append(res.Comments, comm)
		} else {
			isMerged = true
		}
	}
	return res, isMerged, nil
}
