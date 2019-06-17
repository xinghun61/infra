// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/ptypes"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/bq"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/grpc/grpcutil"

	admin "infra/tricium/api/admin/v1"
	apibq "infra/tricium/api/bigquery"
	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	gc "infra/tricium/appengine/common/gerrit"
	"infra/tricium/appengine/common/track"
)

const (
	maxComments = 50
)

// ReportResults processes one report results request.
func (r *gerritReporterServer) ReportResults(c context.Context, req *admin.ReportResultsRequest) (res *admin.ReportResultsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	if req.RunId == 0 {
		return nil, errors.New("missing run ID", grpcutil.InvalidArgumentTag)
	}
	if err := reportResults(c, req, gc.GerritServer); err != nil {
		return nil, errors.Annotate(err, "failed to report results").
			Tag(grpcutil.InternalTag).Err()
	}
	return &admin.ReportResultsResponse{}, nil
}

func reportResults(c context.Context, req *admin.ReportResultsRequest, gerrit gc.API) error {
	// Get Git details first, since other things depend on this.
	request := &track.AnalyzeRequest{ID: req.RunId}
	if err := ds.Get(c, request); err != nil {
		return errors.Annotate(err, "failed to get AnalyzeRequest").Err()
	}
	var includedComments []*track.Comment
	err := parallel.FanOutIn(func(taskC chan<- func() error) {

		// Get comments.
		taskC <- func() error {
			requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
			runKey := ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
			analyzerKey := ds.NewKey(c, "FunctionRun", req.Analyzer, 0, runKey)
			var fetchedComments []*track.Comment
			if err := ds.GetAll(c, ds.NewQuery("Comment").Ancestor(analyzerKey), &fetchedComments); err != nil {
				return errors.Annotate(err, "failed to retrieve comments").Err()
			}

			// Only gather comments selected to be included.
			for _, comment := range fetchedComments {
				commentKey := ds.KeyForObj(c, comment)
				selection := &track.CommentSelection{ID: 1, Parent: commentKey}
				if err := ds.Get(c, selection); err != nil {
					return errors.Annotate(err, "failed to get CommentSelection").Err()
				}
				if selection.Included {
					includedComments = append(includedComments, comment)
				}
			}
			return nil
		}
	})
	if err != nil {
		return err
	}
	if request.GerritReportingDisabled {
		logging.Fields{
			"project": request.Project,
		}.Infof(c, "Gerrit reporting disabled, not reporting results.")
		return nil
	}
	if len(includedComments) > maxComments {
		logging.Fields{
			"numComments": len(includedComments),
			"maxComments": maxComments,
		}.Infof(c, "Too many comments, not reporting results.")
		return nil
	}
	if len(includedComments) == 0 {
		logging.Infof(c, "No comments to report.")
		return nil
	}

	if err := streamCommentsToBigQuery(c, includedComments); err != nil {
		logging.WithError(err).Errorf(c, "Failed to prepare to send rows to BigQuery.")
	}

	return gerrit.PostRobotComments(c, request.GerritHost, request.GerritChange, request.GitRef, req.RunId, includedComments)
}

// streamCommentsToBigQuery adds an event row for the event of sending comments.
//
// The comments here should be only the included comments that will actually be
// sent to Gerrit. The purpose of adding rows to the events table for all
// posted comments is to make it easier to compare the number of feedback
// events for comments to the total number of comments sent.
func streamCommentsToBigQuery(c context.Context, comments []*track.Comment) error {
	// The time that's use for the event is the creation time of the first
	// comment in the slice; we use; by using this time, the time used for the
	// BQ row is determined deterministically based on something else, and
	// could be backfilled from datastore.
	if len(comments) == 0 {
		return errors.New("streamCommentsToBigQuery unexpectedly called when posting zero comments")
	}
	time, err := ptypes.TimestampProto(comments[0].CreationTime)
	if err != nil {
		return errors.Annotate(err, "failed to get comment timestamp").Err()
	}
	var commentMessages []*tricium.Data_Comment
	for _, c := range comments {
		message := &tricium.Data_Comment{}
		if err := jsonpb.UnmarshalString(string(c.Comment), message); err != nil {
			return errors.Annotate(err, "failed to unmarshal comment message").Err()
		}
		commentMessages = append(commentMessages, message)
	}
	event := &apibq.FeedbackEvent{
		Type:     apibq.FeedbackEvent_COMMENT_POST,
		Time:     time,
		Comments: commentMessages,
	}
	if err := common.EventsLog.Insert(c, &bq.Row{Message: event}); err != nil {
		return errors.Annotate(err, "failed in add row to bqlog.Log").Err()
	}
	return nil
}
