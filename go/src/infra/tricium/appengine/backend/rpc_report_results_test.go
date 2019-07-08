// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	"github.com/golang/protobuf/jsonpb"
	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"

	admin "infra/tricium/api/admin/v1"
	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	gc "infra/tricium/appengine/common/gerrit"
	"infra/tricium/appengine/common/track"
	"infra/tricium/appengine/common/triciumtest"
)

func TestReportResultsRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()

		// Add request -> run -> function -> worker to datastore.
		functionName := "MyLinter"
		request := &track.AnalyzeRequest{
			GitURL: "https://chromium-review.googlesource.com",
			GitRef: "refs/changes/88/508788/1",
			Files: []tricium.Data_File{
				{Path: "dir/file.txt"},
			},
		}
		So(ds.Put(ctx, request), ShouldBeNil)
		requestKey := ds.KeyForObj(ctx, request)
		run := &track.WorkflowRun{ID: 1, Parent: requestKey}
		So(ds.Put(ctx, run), ShouldBeNil)
		runKey := ds.KeyForObj(ctx, run)
		So(ds.Put(ctx, &track.FunctionRun{
			ID:     "MyLinter",
			Parent: runKey,
		}), ShouldBeNil)
		analyzerKey := ds.NewKey(ctx, "FunctionRun", "MyLinter", 0, runKey)
		So(ds.Put(ctx, &track.FunctionRunResult{
			ID:          1,
			Parent:      analyzerKey,
			Name:        "MyLinter",
			NumComments: 2,
		}), ShouldBeNil)
		workerName := "MyLinter_UBUNTU"
		So(ds.Put(ctx, &track.WorkerRun{
			ID:     workerName,
			Parent: analyzerKey,
		}), ShouldBeNil)

		// Add example Comment and associated CommentSelection entities.
		workerKey := ds.NewKey(ctx, "WorkerRun", workerName, 0, analyzerKey)

		changedLines := gc.ChangedLinesInfo{
			"dir/file.txt": {2, 5, 6},
		}
		deletedFileCommentJSON, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
			Category: "L",
			Message:  "Line too long",
			Path:     "dir/deleted_file.txt",
		})
		inChangeCommentJSON, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
			Category:  "L",
			Message:   "Line too short",
			Path:      "dir/file.txt",
			StartLine: 2,
			EndLine:   3,
		})
		So(err, ShouldBeNil)
		comments := []*track.Comment{
			{Parent: workerKey, Comment: []byte(deletedFileCommentJSON)},
			{Parent: workerKey, Comment: []byte(inChangeCommentJSON)},
			{Parent: workerKey, Comment: []byte(inChangeCommentJSON)},
		}
		So(ds.Put(ctx, comments), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, comments[0]),
			Included: true,
		}), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{
			ID: 1, Parent: ds.KeyForObj(ctx, comments[1]),
			Included: true,
		}), ShouldBeNil)
		// The third comment added is not "included" when reporting
		// comments.
		So(ds.Put(ctx, &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, comments[2]),
			Included: false,
		}), ShouldBeNil)

		Convey("Reports only included comments", func() {
			mock := &gc.MockRestAPI{ChangedLines: changedLines}
			err = reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: "MyLinter",
			}, mock)
			So(err, ShouldBeNil)
			// This only includes the two selected comments.
			So(len(mock.LastComments), ShouldEqual, len(comments)-1)

			Convey("A successful request also sends a row to BQ", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.FeedbackEventsQueue]), ShouldEqual, 1)
			})
		})

		Convey("Does not report results when reporting is disabled", func() {
			request.GerritReportingDisabled = true
			So(ds.Put(ctx, request), ShouldBeNil)
			mock := &gc.MockRestAPI{ChangedLines: changedLines}
			err = reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: functionName,
			}, mock)
			So(err, ShouldBeNil)
			So(len(mock.LastComments), ShouldEqual, 0)

			Convey("When no comments are posted, no rows are sent to BQ", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.FeedbackEventsQueue]), ShouldEqual, 0)
			})
		})

		// Put more comments in until the number of included comments
		// has reached the maximum comment number threshold.
		for len(comments) < maxComments+1 {
			comment := &track.Comment{Parent: workerKey, Comment: []byte(deletedFileCommentJSON)}
			comments = append(comments, comment)
			So(ds.Put(ctx, comment), ShouldBeNil)
			So(ds.Put(ctx, &track.CommentSelection{
				ID:       1,
				Parent:   ds.KeyForObj(ctx, comment),
				Included: true,
			}), ShouldBeNil)
		}
		So(len(comments), ShouldEqual, maxComments+1)

		Convey("Reports when number of comments is at maximum", func() {
			mock := &gc.MockRestAPI{ChangedLines: changedLines}
			err = reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: functionName,
			}, mock)
			So(err, ShouldBeNil)
			So(len(mock.LastComments), ShouldEqual, maxComments)
		})

		// This comment is not on a changed line.
		outsideChangeCommentJSON, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
			Category:  "L",
			Message:   "Line too short",
			Path:      "dir/file.txt",
			StartLine: 3,
			EndLine:   3,
		})
		// Put the new comment with line numbers in.
		outsideChangeComment := &track.Comment{Parent: workerKey, Comment: []byte(outsideChangeCommentJSON)}
		comments = append(comments, outsideChangeComment)
		So(ds.Put(ctx, outsideChangeComment), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, outsideChangeComment),
			Included: gc.CommentIsInChangedLines(ctx, outsideChangeComment, changedLines),
		}), ShouldBeNil)
		So(len(comments), ShouldEqual, maxComments+2)

		Convey("Does not report comments that are not on changed lines", func() {
			mock := &gc.MockRestAPI{ChangedLines: changedLines}
			err := reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: functionName,
			}, mock)
			So(err, ShouldBeNil)
			So(len(mock.LastComments), ShouldEqual, maxComments)
		})

		// Put one more comment in;
		comment := &track.Comment{Parent: workerKey, Comment: []byte(deletedFileCommentJSON)}
		comments = append(comments, comment)
		So(ds.Put(ctx, comment), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, comment),
			Included: gc.CommentIsInChangedLines(ctx, comment, changedLines),
		}), ShouldBeNil)
		So(len(comments), ShouldEqual, maxComments+3)

		Convey("Does not report when number of comments exceeds maximum", func() {
			mock := &gc.MockRestAPI{ChangedLines: changedLines}
			err := reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: functionName,
			}, mock)
			So(err, ShouldBeNil)
			So(len(mock.LastComments), ShouldEqual, 0)
		})
	})
}

func TestReportResultsRequestWithRenamedOrCopiedFiles(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()

		// Add request -> run -> function -> worker to datastore.
		request := &track.AnalyzeRequest{
			GitURL: "https://chromium-review.googlesource.com",
			GitRef: "refs/changes/88/508788/1",
			Files: []tricium.Data_File{
				{Path: "dir/file.txt"},
				{Path: "dir/renamed_file.txt", Status: tricium.Data_RENAMED},
				{Path: "dir/copied_file.txt", Status: tricium.Data_COPIED},
			},
		}
		So(ds.Put(ctx, request), ShouldBeNil)
		requestKey := ds.KeyForObj(ctx, request)
		run := &track.WorkflowRun{ID: 1, Parent: requestKey}
		So(ds.Put(ctx, run), ShouldBeNil)
		runKey := ds.KeyForObj(ctx, run)
		So(ds.Put(ctx, &track.FunctionRun{
			ID:     "MyLinter",
			Parent: runKey,
		}), ShouldBeNil)
		analyzerKey := ds.NewKey(ctx, "FunctionRun", "MyLinter", 0, runKey)
		So(ds.Put(ctx, &track.FunctionRunResult{
			ID:          1,
			Parent:      analyzerKey,
			Name:        "MyLinter",
			NumComments: 2,
		}), ShouldBeNil)
		workerName := "MyLinter_UBUNTU"
		So(ds.Put(ctx, &track.WorkerRun{
			ID:     workerName,
			Parent: analyzerKey,
		}), ShouldBeNil)

		// Add example Comment and associated CommentSelection entities.
		workerKey := ds.NewKey(ctx, "WorkerRun", workerName, 0, analyzerKey)

		changedLines := gc.ChangedLinesInfo{
			"dir/file.txt":         {2, 5, 6},
			"dir/renamed_file.txt": {1, 2, 3, 4, 5, 6, 7},
			"dir/copied_file.txt":  {1, 2, 3, 4, 5, 6, 7},
		}
		gc.FilterRequestChangedLines(request, &changedLines)
		inChangeCommentJSON, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
			Category:  "L",
			Message:   "Line too short",
			Path:      "dir/file.txt",
			StartLine: 2,
			EndLine:   3,
		})
		inRenamedFileCommentJSON, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
			Category:  "L",
			Message:   "Line doesn't look right",
			Path:      "dir/renamed_file.txt",
			StartLine: 2,
			EndLine:   3,
		})
		inCopiedFileCommentJSON, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
			Category:  "L",
			Message:   "Line doesn't look right",
			Path:      "dir/copied_file.txt",
			StartLine: 2,
			EndLine:   3,
		})
		So(err, ShouldBeNil)
		comments := []*track.Comment{
			{Parent: workerKey, Comment: []byte(inChangeCommentJSON)},
			{Parent: workerKey, Comment: []byte(inRenamedFileCommentJSON)},
			{Parent: workerKey, Comment: []byte(inCopiedFileCommentJSON)},
		}
		So(ds.Put(ctx, comments), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, comments[0]),
			Included: gc.CommentIsInChangedLines(ctx, comments[0], changedLines),
		}), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, comments[1]),
			Included: gc.CommentIsInChangedLines(ctx, comments[1], changedLines),
		}), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, comments[2]),
			Included: gc.CommentIsInChangedLines(ctx, comments[2], changedLines),
		}), ShouldBeNil)

		Convey("Does not report comments in renamed or copied files", func() {
			mock := &gc.MockRestAPI{ChangedLines: changedLines}
			err := reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: "MyLinter",
			}, mock)
			So(err, ShouldBeNil)
			So(len(mock.LastComments), ShouldEqual, 1)
		})
	})
}
