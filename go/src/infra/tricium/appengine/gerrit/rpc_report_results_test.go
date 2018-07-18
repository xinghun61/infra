// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"testing"

	"github.com/golang/protobuf/jsonpb"
	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
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

		changedLines := ChangedLinesInfo{"file": {2, 5, 6}}
		json1, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
			Category: "L",
			Message:  "Line too long",
			Path:     "deleted_file",
		})
		json2, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
			Category:  "L",
			Message:   "Line too short",
			Path:      "file",
			StartLine: 2,
			EndLine:   3,
		})
		So(err, ShouldBeNil)
		comments := []*track.Comment{
			{Parent: workerKey, Comment: []byte(json1)},
			{Parent: workerKey, Comment: []byte(json2)},
			{Parent: workerKey, Comment: []byte(json2)},
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
			mock := &mockRestAPI{ChangedLines: changedLines}
			err := reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: "MyLinter",
			}, mock)
			So(err, ShouldBeNil)
			// This only includes the two selected comments.
			So(len(mock.LastComments), ShouldEqual, len(comments)-1)
		})

		Convey("Does not report results when reporting is disabled", func() {
			request.GerritReportingDisabled = true
			So(ds.Put(ctx, request), ShouldBeNil)
			mock := &mockRestAPI{ChangedLines: changedLines}
			err := reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: functionName,
			}, mock)
			So(err, ShouldBeNil)
			So(len(mock.LastComments), ShouldEqual, 0)
		})

		// Put more comments in until the number of included comments
		// has reached the maximum comment number threshold.
		for len(comments) < maxComments+1 {
			comment := &track.Comment{Parent: workerKey, Comment: []byte(json1)}
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
			mock := &mockRestAPI{ChangedLines: changedLines}
			err := reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: functionName,
			}, mock)
			So(err, ShouldBeNil)
			So(len(mock.LastComments), ShouldEqual, maxComments)
		})

		json3, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
			Category:  "L",
			Message:   "Line too short",
			Path:      "file",
			StartLine: 3,
			EndLine:   3,
		})
		// Put the new comment with line numbers in;
		comment3 := &track.Comment{Parent: workerKey, Comment: []byte(json3)}
		comments = append(comments, comment3)
		So(ds.Put(ctx, comment3), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, comment3),
			Included: true,
		}), ShouldBeNil)
		So(len(comments), ShouldEqual, maxComments+2)

		Convey("Does not report comments that are not on changed lines", func() {
			mock := &mockRestAPI{ChangedLines: changedLines}
			err := reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: functionName,
			}, mock)
			So(err, ShouldBeNil)
			So(len(mock.LastComments), ShouldEqual, maxComments)
		})

		// Put one more comment in;
		comment := &track.Comment{Parent: workerKey, Comment: []byte(json1)}
		comments = append(comments, comment)
		So(ds.Put(ctx, comment), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, comment),
			Included: true,
		}), ShouldBeNil)
		So(len(comments), ShouldEqual, maxComments+3)

		Convey("Does not report when number of comments exceeds maximum", func() {
			mock := &mockRestAPI{ChangedLines: changedLines}
			err := reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: functionName,
			}, mock)
			So(err, ShouldBeNil)
			So(len(mock.LastComments), ShouldEqual, 0)
		})
	})
}

func TestCommentIsInChangedLines(t *testing.T) {
	Convey("Test Environment", t, func() {

		ctx := triciumtest.Context()

		Convey("Single line comment in changed lines", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "dir/file.txt",
				StartLine: 5,
				EndLine:   5,
				StartChar: 0,
				EndChar:   10,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(commentIsInChangedLines(ctx, comment, lines), ShouldBeTrue)
		})

		Convey("Single line comment outside of changed lines", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "dir/file.txt",
				StartLine: 4,
				EndLine:   4,
				StartChar: 0,
				EndChar:   10,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(commentIsInChangedLines(ctx, comment, lines), ShouldBeFalse)
		})

		Convey("Single line comment outside of changed files", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "DELETED.txt",
				StartLine: 5,
				EndLine:   5,
				StartChar: 5,
				EndChar:   10,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(commentIsInChangedLines(ctx, comment, lines), ShouldBeFalse)
		})

		Convey("Comment with line range that overlaps changed line", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "dir/file.txt",
				StartLine: 3,
				EndLine:   8,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(commentIsInChangedLines(ctx, comment, lines), ShouldBeTrue)
		})

		Convey("Comment with end char == 0, implying end line is not included", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "dir/file.txt",
				StartLine: 6,
				EndLine:   10,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(commentIsInChangedLines(ctx, comment, lines), ShouldBeFalse)
		})

		Convey("File-level comments are included", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path: "dir/file.txt",
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(commentIsInChangedLines(ctx, comment, lines), ShouldBeTrue)
		})

		Convey("Line comments on changed lines are included", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "dir/file.txt",
				StartLine: 2,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(commentIsInChangedLines(ctx, comment, lines), ShouldBeTrue)
		})
	})
}

func TestIsInChangedLines(t *testing.T) {
	Convey("Overlapping cases", t, func() {
		So(isInChangedLines(1, 3, []int{2, 3, 4}), ShouldBeTrue)
		So(isInChangedLines(4, 5, []int{2, 3, 4}), ShouldBeTrue)
		// The end line is inclusive.
		So(isInChangedLines(1, 2, []int{2, 3, 4}), ShouldBeTrue)
		So(isInChangedLines(3, 3, []int{2, 3, 4}), ShouldBeTrue)
	})

	Convey("Non-overlapping cases", t, func() {
		So(isInChangedLines(5, 6, []int{2, 3, 4}), ShouldBeFalse)
		So(isInChangedLines(1, 1, []int{2, 3, 4}), ShouldBeFalse)
	})

	Convey("Invalid range cases", t, func() {
		So(isInChangedLines(2, 0, []int{2, 3, 4}), ShouldBeFalse)
	})
}
