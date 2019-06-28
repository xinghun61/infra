// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"strconv"

	"github.com/golang/protobuf/jsonpb"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/grpcutil"

	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

// Results processes one results request to Tricium.
func (r *TriciumServer) Results(c context.Context, req *tricium.ResultsRequest) (res *tricium.ResultsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	logging.Fields{
		"runID": req.RunId,
	}.Infof(c, "Request received.")
	if req.RunId == "" {
		return nil, errors.Reason("missing run ID").Tag(grpcutil.InvalidArgumentTag).Err()
	}
	runID, err := strconv.ParseInt(req.RunId, 10, 64)
	if err != nil {
		return nil, errors.Annotate(err, "invalid run ID %s", req.RunId).Tag(grpcutil.InvalidArgumentTag).Err()
	}
	results, isMerged, err := results(c, runID)
	if err != nil {
		return nil, errors.Annotate(err, "results request failed").Tag(grpcutil.InternalTag).Err()
	}
	logging.Fields{
		"results": results,
	}.Infof(c, "Request completed.")
	return &tricium.ResultsResponse{Results: results, IsMerged: isMerged}, nil
}

func results(c context.Context, runID int64) (*tricium.Data_Results, bool, error) {
	comments, err := track.FetchComments(c, runID)
	if err != nil {
		return nil, false, errors.Annotate(err, "failed to get Comments").Err()
	}
	isMerged := false
	res := &tricium.Data_Results{}
	for _, comment := range comments {
		commentKey := ds.KeyForObj(c, comment)
		cr := &track.CommentSelection{ID: 1, Parent: commentKey}
		if err := ds.Get(c, cr); err != nil {
			return nil, false, errors.Annotate(err, "failed to get CommentSelection").Err()
		}
		if cr.Included {
			comm := &tricium.Data_Comment{}
			if err := jsonpb.UnmarshalString(string(comment.Comment), comm); err != nil {
				return nil, false, errors.Annotate(err, "failed to unmarshal comment").Err()
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
		return res, isMerged, errors.Annotate(err, "failed to get AnalyzeRequest").Err()
	}
	resultsRequestCount.Add(c, 1, request.Project, strconv.FormatInt(runID, 10))
	return res, isMerged, nil
}
