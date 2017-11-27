// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	ds "go.chromium.org/gae/service/datastore"

	"infra/tricium/api/v1"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

func TestReport(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		commentID := "7ef59cda-183c-48b3-8343-d9036a7f1419"
		analyzerName := "Spacey"
		platform := tricium.Platform_UBUNTU
		// Add comment entity with ancestors:
		// AnalyzerRequest>WorkflowRun>AnalyzerRun>WorkerRun>Comment>CommentFeedback
		request := &track.AnalyzeRequest{}
		So(ds.Put(ctx, request), ShouldBeNil)
		run := &track.WorkflowRun{ID: 1, Parent: ds.KeyForObj(ctx, request)}
		So(ds.Put(ctx, run), ShouldBeNil)
		analyzer := &track.AnalyzerRun{ID: analyzerName, Parent: ds.KeyForObj(ctx, run)}
		So(ds.Put(ctx, analyzer), ShouldBeNil)
		worker := &track.WorkerRun{
			ID:     fmt.Sprintf("%s_%s", analyzerName, platform),
			Parent: ds.KeyForObj(ctx, analyzer),
		}
		So(ds.Put(ctx, worker), ShouldBeNil)
		comment := &track.Comment{UUID: commentID, Parent: ds.KeyForObj(ctx, worker), Platforms: 1}
		So(ds.Put(ctx, comment), ShouldBeNil)
		feedback := &track.CommentFeedback{ID: 1, Parent: ds.KeyForObj(ctx, comment)}
		So(ds.Put(ctx, feedback), ShouldBeNil)

		Convey("Report not useful request", func() {
			Convey("For known comment ID", func() {
				_, err := report(ctx, commentID, "")
				So(err, ShouldBeNil)
			})
			Convey("For unknown comment ID", func() {
				_, err := report(ctx, "abcdefg-hijklm", "")
				So(err, ShouldNotBeNil)
			})
		})

		Convey("Validates valid request", func() {
			err := validateReportRequest(ctx, &tricium.ReportNotUsefulRequest{
				CommentId:   commentID,
				MoreDetails: "Some more info",
			})
			So(err, ShouldBeNil)
		})

		Convey("Fails invalid request", func() {
			err := validateReportRequest(ctx, &tricium.ReportNotUsefulRequest{
				MoreDetails: "More info", // missing comment ID
			})
			So(err, ShouldNotBeNil)
		})
	})
}
