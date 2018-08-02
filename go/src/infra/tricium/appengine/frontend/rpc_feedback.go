// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"strings"
	"time"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

// Feedback processes one feedback request to Tricium.
func (r *TriciumServer) Feedback(c context.Context, req *tricium.FeedbackRequest) (res *tricium.FeedbackResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	logging.Fields{
		"category":   req.Category,
		"start_time": req.StartTime,
		"end_time":   req.EndTime,
	}.Infof(c, "[frontend] Feedback request received.")
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
// Start and end time can be empty, in which case the intent is to have
// an open-ended range. No start or end is meant to mean "all time".
//
// The returned error should be tagged for gRPC by the caller.
func parseTimeRange(c context.Context, start, end string) (time.Time, time.Time, error) {
	stime := time.Unix(0, 0).UTC() // Beginning of Unix time.
	etime := clock.Now(c).UTC()
	var err error
	if start != "" {
		stime, err = time.Parse(time.RFC3339, start)
		if err != nil {
			return stime, etime, errors.Annotate(err, "invalid start_time").Err()
		}
	}
	if end != "" {
		etime, err = time.Parse(time.RFC3339, end)
		if err != nil {
			return stime, etime, errors.Annotate(err, "invalid end_time").Err()
		}
	}
	if etime.Before(stime) {
		return stime, etime, errors.New("start_time/end_time out of order")
	}
	return stime, etime, nil
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
			"category":   category,
			"start time": stime.String(),
			"end time":   etime.String(),
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
