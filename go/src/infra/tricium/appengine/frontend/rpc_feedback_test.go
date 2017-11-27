// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"testing"
	"time"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock/testclock"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/v1"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

func TestFeedback(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()
		now := time.Date(2017, 1, 1, 0, 0, 0, 0, time.UTC)
		ctx, tc := testclock.UseTime(ctx, now)
		ds.GetTestable(ctx).AddIndexes(&ds.IndexDefinition{
			Kind: "Comment",
			SortBy: []ds.IndexColumn{
				{Property: "Analyzer"},
				{Property: "CreationTime"},
			},
		})
		ds.GetTestable(ctx).CatchupIndexes()
		// Add comment entities with ancestors:
		// AnalyzerRequest>WorkflowRun>AnalyzerRun>WorkerRun>Comment>CommentFeedback
		stime := tc.Now().UTC().Add(3 * time.Minute)
		etime := tc.Now().UTC().Add(7 * time.Minute)
		ctime1 := tc.Now().UTC().Add(2 * time.Minute) // before stime
		ctime2 := tc.Now().UTC().Add(4 * time.Minute) // between stime and etime
		ctx, _ = testclock.UseTime(ctx, now.Add(10*time.Minute))
		commentID1 := "7ef59cda-183c-48b3-8343-d9036a7f1419"
		commentID2 := "9400f12d-b425-4cf6-85d5-5636fc4e55a4"
		analyzerName := "Spacey"
		category1 := "Spacey/MixedSpace"
		category2 := "Spacey/TrailingSpace"
		platform := tricium.Platform_UBUNTU
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
		comment1 := &track.Comment{
			UUID:         commentID1,
			Parent:       ds.KeyForObj(ctx, worker),
			Platforms:    1,
			Analyzer:     analyzerName,
			Category:     category1,
			CreationTime: ctime1,
		}
		So(ds.Put(ctx, comment1), ShouldBeNil)
		feedback1 := &track.CommentFeedback{
			ID:               1,
			Parent:           ds.KeyForObj(ctx, comment1),
			NotUsefulReports: 2,
		}
		So(ds.Put(ctx, feedback1), ShouldBeNil)
		selection1 := &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, comment1),
			Included: true,
		}
		So(ds.Put(ctx, selection1), ShouldBeNil)
		comment2 := &track.Comment{
			UUID:         commentID2,
			Parent:       ds.KeyForObj(ctx, worker),
			Platforms:    1,
			Analyzer:     analyzerName,
			Category:     category2,
			CreationTime: ctime2,
		}
		So(ds.Put(ctx, comment2), ShouldBeNil)
		feedback2 := &track.CommentFeedback{
			ID:               1,
			Parent:           ds.KeyForObj(ctx, comment2),
			NotUsefulReports: 1,
			NotUsefulIssueURLs: []string{
				"https://bugs.chromium.org/p/chromium/issues/detail?id=775017",
			},
		}
		So(ds.Put(ctx, feedback2), ShouldBeNil)
		selection2 := &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, comment2),
			Included: true,
		}
		So(ds.Put(ctx, selection2), ShouldBeNil)

		Convey("Feedback request for unknown category", func() {
			st, et, _ := validateFeedbackRequest(ctx, &tricium.FeedbackRequest{Category: "Hello"})
			count, reports, issues, err := feedback(ctx, "Hello", st, et)
			So(err, ShouldBeNil)
			So(count, ShouldEqual, 0)
			So(reports, ShouldEqual, 0)
			So(issues, ShouldBeNil)
		})

		Convey("Feedback request for known analyzer name", func() {
			st, et, _ := validateFeedbackRequest(ctx, &tricium.FeedbackRequest{Category: analyzerName})
			count, reports, issues, err := feedback(ctx, analyzerName, st, et)
			So(err, ShouldBeNil)
			So(count, ShouldEqual, 2)
			So(reports, ShouldEqual, 3)
			So(issues, ShouldNotBeNil)
			So(len(issues), ShouldEqual, 1)
		})

		Convey("Feedback request for time period", func() {
			count, reports, issues, err := feedback(ctx, analyzerName, stime, etime)
			So(err, ShouldBeNil)
			So(count, ShouldEqual, 1)
			So(reports, ShouldEqual, 1)
			So(issues, ShouldNotBeNil)
			So(len(issues), ShouldEqual, 1)
		})

		Convey("Feedback request for subcategory", func() {
			st, et, _ := validateFeedbackRequest(ctx, &tricium.FeedbackRequest{Category: category1})
			count, reports, issues, err := feedback(ctx, category1, st, et)
			So(err, ShouldBeNil)
			So(count, ShouldEqual, 1)
			So(reports, ShouldEqual, 2)
			So(issues, ShouldBeNil)
		})

		Convey("Validates valid request", func() {
			_, _, err := validateFeedbackRequest(ctx, &tricium.FeedbackRequest{
				Category:  category1,
				StartTime: stime.Format(longForm),
				EndTime:   etime.Format(longForm),
			})
			So(err, ShouldBeNil)
		})

		Convey("Fails invalid request", func() {
			_, _, err := validateFeedbackRequest(ctx, &tricium.FeedbackRequest{
				Category:  category1,
				StartTime: etime.Format(longForm), // times in wrong order
				EndTime:   stime.Format(longForm),
			})
			So(err, ShouldNotBeNil)
		})
	})
}
