// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"strings"
	"time"

	"github.com/golang/protobuf/ptypes"
	"github.com/golang/protobuf/ptypes/timestamp"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/grpcutil"

	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

// Feedback processes one feedback request to Tricium.
func (r *TriciumServer) Feedback(c context.Context, req *tricium.FeedbackRequest) (res *tricium.FeedbackResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	logging.Fields{
		"project":   req.Project,
		"category":  req.Category,
		"startTime": req.StartTime,
		"endTime":   req.EndTime,
	}.Infof(c, "Request received.")
	if req.Category == "" {
		return nil, errors.New("missing category", grpcutil.InvalidArgumentTag)
	}
	stime, etime, err := parseTimeRange(c, req.StartTime, req.EndTime)
	if err != nil {
		return nil, errors.Annotate(err, "invalid time range").Tag(grpcutil.InvalidArgumentTag).Err()
	}
	count, reports, err := feedback(c, req.Category, stime, etime)
	if err != nil {
		return nil, err
	}
	return &tricium.FeedbackResponse{Comments: int32(count), NotUsefulReports: int32(reports)}, nil
}

// parseTimeRange returns the parsed time range and checks for validity.
//
// Start and end time can be nil, in which case the intent is to have
// an open-ended range. No start or end is meant to mean "all time".
func parseTimeRange(c context.Context, startTimestamp, endTimestamp *timestamp.Timestamp) (time.Time, time.Time, error) {
	startTime := time.Unix(0, 0).UTC()
	endTime := clock.Now(c).UTC()
	var err error
	if startTimestamp != nil {
		startTime, err = ptypes.Timestamp(startTimestamp)
		if err != nil {
			return startTime, endTime, errors.Annotate(err, "failed to convert start_time").Err()
		}
	}
	if endTimestamp != nil {
		endTime, err = ptypes.Timestamp(endTimestamp)
		if err != nil {
			return startTime, endTime, errors.Annotate(err, "failed to convert end_time").Err()
		}
	}
	if endTime.Before(startTime) {
		return startTime, endTime, errors.New("start_time/end_time out of order")
	}
	return startTime, endTime, nil
}

func feedback(c context.Context, category string, stime, etime time.Time) (int, int, error) {
	// Extract analyzer name from category.
	analyzer := strings.SplitN(category, "/", 2)[0]
	// Getting all comments for the provided category.
	// Note that this includes potentially not selected comments, but these comments are not
	// exposed for feedback which means they have no feedback data to contribute.
	var comments []*track.Comment
	if err := ds.GetAll(c, ds.NewQuery("Comment").Eq("Analyzer", analyzer).Gte("CreationTime", stime).Lte("CreationTime", etime), &comments); err != nil {
		return 0, 0, errors.Annotate(err, "failed to retrieve Comment entities").Err()
	}
	if len(comments) == 0 {
		logging.Fields{
			"category":  category,
			"startTime": stime.String(),
			"endTime":   etime.String(),
		}.Infof(c, "Found no comments.")
	}
	var entities []interface{}
	for _, comment := range comments {
		// Only include comments with the same prefix as the requested category.
		// This enables narrowing of summaries to subcategories.
		if strings.HasPrefix(comment.Category, category) {
			commentKey := ds.KeyForObj(c, comment)
			entities = append(entities, &track.CommentFeedback{ID: 1, Parent: commentKey})
			entities = append(entities, &track.CommentSelection{ID: 1, Parent: commentKey})
		}
	}
	if err := ds.Get(c, entities); err != nil {
		return 0, 0, errors.Annotate(err, "failed to retrieve CommentFeedback entities").Err()
	}
	count := 0
	reports := 0
	for _, entity := range entities {
		switch t := entity.(type) {
		case *track.CommentFeedback:
			reports += t.NotUsefulReports
		case *track.CommentSelection:
			if t.Included {
				count++
			}
		}
	}
	return count, reports, nil
}
