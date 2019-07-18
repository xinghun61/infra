// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"testing"

	"github.com/golang/protobuf/jsonpb"
	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"

	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/track"
	"infra/tricium/appengine/common/triciumtest"
)

func TestReportNotUseful(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()
		commentID := "7ef59cda-183c-48b3-8343-d9036a7f1419"
		functionName := "Spacey"
		platform := tricium.Platform_UBUNTU

		// Add comment entity with ancestors:
		// AnalyzeRequest>WorkflowRun>FunctionRun>WorkerRun>Comment>CommentFeedback
		request := &track.AnalyzeRequest{}
		So(ds.Put(ctx, request), ShouldBeNil)
		run := &track.WorkflowRun{ID: 1, Parent: ds.KeyForObj(ctx, request)}
		So(ds.Put(ctx, run), ShouldBeNil)
		function := &track.FunctionRun{
			ID:                functionName,
			Parent:            ds.KeyForObj(ctx, run),
			Owner:             "qyearsley@chromium.org",
			MonorailComponent: "Infra>Platform>Tricium",
		}
		So(ds.Put(ctx, function), ShouldBeNil)
		worker := &track.WorkerRun{
			ID:     fmt.Sprintf("%s_%s", functionName, platform),
			Parent: ds.KeyForObj(ctx, function),
		}
		So(ds.Put(ctx, worker), ShouldBeNil)
		json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
			Path:      "dir/file.txt",
			Message:   "comment message",
			StartLine: 4,
		})
		So(err, ShouldBeNil)
		comment := &track.Comment{
			UUID:      commentID,
			Comment:   []byte(json),
			Parent:    ds.KeyForObj(ctx, worker),
			Platforms: 1,
		}
		So(ds.Put(ctx, comment), ShouldBeNil)
		feedback := &track.CommentFeedback{ID: 1, Parent: ds.KeyForObj(ctx, comment)}
		So(ds.Put(ctx, feedback), ShouldBeNil)

		Convey("Single request for known comment increments count", func() {
			request := &tricium.ReportNotUsefulRequest{CommentId: commentID}
			response, err := server.ReportNotUseful(ctx, request)
			So(err, ShouldBeNil)
			So(response, ShouldResemble, &tricium.ReportNotUsefulResponse{
				Owner:             "qyearsley@chromium.org",
				MonorailComponent: "Infra>Platform>Tricium",
			})
			So(ds.Get(ctx, feedback), ShouldBeNil)
			So(feedback.NotUsefulReports, ShouldEqual, 1)

			Convey("A successful request also sends a row to BQ", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.FeedbackEventsQueue]), ShouldEqual, 1)
			})
		})

		Convey("Request for unknown comment gives error", func() {
			request := &tricium.ReportNotUsefulRequest{CommentId: "abcdefg"}
			response, err := server.ReportNotUseful(ctx, request)
			So(err, ShouldNotBeNil)
			So(response, ShouldBeNil)
			So(ds.Get(ctx, feedback), ShouldBeNil)
			So(feedback.NotUsefulReports, ShouldEqual, 0)

			Convey("An unsuccessful request sends no row to BQ", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.FeedbackEventsQueue]), ShouldEqual, 0)
			})
		})

		Convey("Request with no comment gives error", func() {
			request := &tricium.ReportNotUsefulRequest{}
			response, err := server.ReportNotUseful(ctx, request)
			So(err, ShouldNotBeNil)
			So(response, ShouldBeNil)
			So(ds.Get(ctx, feedback), ShouldBeNil)
			So(feedback.NotUsefulReports, ShouldEqual, 0)
		})

		Convey("Two requests increment twice and have the same response", func() {
			request := &tricium.ReportNotUsefulRequest{CommentId: commentID}
			response, err := server.ReportNotUseful(ctx, request)
			So(err, ShouldBeNil)
			So(response, ShouldResemble, &tricium.ReportNotUsefulResponse{
				Owner:             "qyearsley@chromium.org",
				MonorailComponent: "Infra>Platform>Tricium",
			})
			response, err = server.ReportNotUseful(ctx, request)
			So(err, ShouldBeNil)
			So(response, ShouldResemble, &tricium.ReportNotUsefulResponse{
				Owner:             "qyearsley@chromium.org",
				MonorailComponent: "Infra>Platform>Tricium",
			})
			So(ds.Get(ctx, feedback), ShouldBeNil)
			So(feedback.NotUsefulReports, ShouldEqual, 2)
		})
	})
}
