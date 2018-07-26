// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"strconv"

	"github.com/golang/protobuf/jsonpb"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"
	"golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

// Results processes one results request to Tricium.
func (r *TriciumServer) Results(c context.Context, req *tricium.ResultsRequest) (*tricium.ResultsResponse, error) {
	logging.Fields{
		"run ID": req.RunId,
	}.Infof(c, "[frontend] Results request received.")
	if req.RunId == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	runID, err := strconv.ParseInt(req.RunId, 10, 64)
	if err != nil {
		return nil, grpc.Errorf(codes.InvalidArgument, "invalid run ID %s: %v", req.RunId, err)
	}
	results, isMerged, err := results(c, runID)
	if err != nil {
		return nil, grpc.Errorf(codes.Internal, "results request failed: %v", err)
	}
	logging.Infof(c, "[frontend] Results request completed: %v", results)
	return &tricium.ResultsResponse{Results: results, IsMerged: isMerged}, nil
}

func results(c context.Context, runID int64) (*tricium.Data_Results, bool, error) {
	comments, err := track.FetchComments(c, runID)
	if err != nil {
		return nil, false, fmt.Errorf("failed to get comments: %v", err)
	}
	isMerged := false
	res := &tricium.Data_Results{}
	for _, comment := range comments {
		commentKey := ds.KeyForObj(c, comment)
		cr := &track.CommentSelection{ID: 1, Parent: commentKey}
		if err := ds.Get(c, cr); err != nil {
			return nil, false, fmt.Errorf("failed to get CommentSelection: %v", err)
		}
		if cr.Included {
			comm := &tricium.Data_Comment{}
			if err := jsonpb.UnmarshalString(string(comment.Comment), comm); err != nil {
				return nil, false, fmt.Errorf("failed to unmarshal comment: %v", err)
			}
			res.Comments = append(res.Comments, comm)
			res.Platforms |= comment.Platforms
		} else {
			isMerged = true
		}
	}
	// Monitor results requests per project and run ID.
	request := &track.AnalyzeRequest{ID: runID}
	if err := ds.Get(c, request); err != nil {
		return res, isMerged, fmt.Errorf("failed to get AnalyzeRequest: %v", err)
	}
	resultsRequestCount.Add(c, 1, request.Project, strconv.FormatInt(runID, 10))
	return res, isMerged, nil
}
