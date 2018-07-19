// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

// ReportNotUseful processes one report not useful request to Tricium.
func (r *TriciumServer) ReportNotUseful(c context.Context,
	req *tricium.ReportNotUsefulRequest) (*tricium.ReportNotUsefulResponse, error) {
	if err := validateReportRequest(c, req); err != nil {
		logging.WithError(err).Errorf(c, "Invalid ReportNotUsefulRequest.")
		return nil, err
	}
	// TODO(qyearsley): Get analyzer owner and component, and include these in the response.
	if err := report(c, req.CommentId); err != nil {
		logging.WithError(err).Errorf(c, "[frontend] Report not useful failed.")
		return nil, grpc.Errorf(codes.Internal, "failed to process report not useful request")
	}
	logging.Fields{
		"comment ID": req.CommentId,
	}.Infof(c, "[frontend] Report not useful request received.")
	return &tricium.ReportNotUsefulResponse{}, nil
}

func validateReportRequest(c context.Context, req *tricium.ReportNotUsefulRequest) error {
	if req.CommentId == "" {
		return grpc.Errorf(codes.InvalidArgument, "missing 'comment_id' field")
	}
	return nil
}

func report(c context.Context, commentID string) error {
	var comments []*track.Comment
	if err := ds.GetAll(c, ds.NewQuery("Comment").Eq("UUID", commentID), &comments); err != nil {
		return fmt.Errorf("failed to get Comment entity: %v", err)
	}
	if len(comments) == 0 {
		return fmt.Errorf("zero comments with UUID: %s", commentID)
	}
	if len(comments) > 1 {
		return fmt.Errorf("multiple comments with the UUID: %s", commentID)
	}
	feedback := &track.CommentFeedback{ID: 1, Parent: ds.KeyForObj(c, comments[0])}
	return ds.RunInTransaction(c, func(c context.Context) error {
		if err := ds.Get(c, feedback); err != nil {
			return fmt.Errorf("failed to get CommentFeedback entity: %v", err)
		}
		// TODO(qyearsley): Add protection against multiple clicks by one user.
		feedback.NotUsefulReports++
		if err := ds.Put(c, feedback); err != nil {
			return fmt.Errorf("failed to store CommentFeedback entity: %v", err)
		}
		return nil
	}, nil)
}
