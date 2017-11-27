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
func (r *TriciumServer) ReportNotUseful(c context.Context, req *tricium.ReportNotUsefulRequest) (*tricium.ReportNotUsefulResponse, error) {
	if err := validateReportRequest(c, req); err != nil {
		return nil, err
	}
	issue, err := report(c, req.CommentId, req.MoreDetails)
	if err != nil {
		logging.WithError(err).Errorf(c, "report not useful failed: %v", err)
		return nil, grpc.Errorf(codes.Internal, "failed to process report not useful request")
	}
	logging.Infof(c, "[frontend] Report not useful, comment ID: %q, issue: %s", req.CommentId, issue)
	return &tricium.ReportNotUsefulResponse{Issue: issue}, nil
}

func validateReportRequest(c context.Context, req *tricium.ReportNotUsefulRequest) error {
	if req.CommentId == "" {
		msg := "missing 'comment_id' field in ReportNotUseful request"
		logging.Errorf(c, msg)
		return grpc.Errorf(codes.InvalidArgument, msg)
	}
	return nil
}

func report(c context.Context, commentID, info string) (string, error) {
	var comments []*track.Comment
	if err := ds.GetAll(c, ds.NewQuery("Comment").Eq("UUID", commentID), &comments); err != nil {
		return "", fmt.Errorf("failed to retrieve Comment entity: %v", err)
	}
	if len(comments) == 0 {
		return "", fmt.Errorf("found no comment with UUID: %s", commentID)
	}
	if len(comments) > 1 {
		return "", fmt.Errorf("multiple comments with the same ID, id: %s", commentID)
	}
	feedback := &track.CommentFeedback{ID: 1, Parent: ds.KeyForObj(c, comments[0])}
	return "", ds.RunInTransaction(c, func(c context.Context) error {
		if err := ds.Get(c, feedback); err != nil {
			return fmt.Errorf("failed to get CommentFeedback entity: %v", err)
		}
		// TODO(emso): Add protection against multiple clicks by one user.
		feedback.NotUsefulReports++
		if info != "" {
			// TODO(emso): Report issue with provided info.
		}
		if err := ds.Put(c, feedback); err != nil {
			return fmt.Errorf("failed to store CommentFeedback entity: %v", err)
		}
		return nil
	}, nil)
}
