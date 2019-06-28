// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"testing"
	"time"

	"github.com/golang/protobuf/ptypes"
	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock/testclock"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
	"infra/tricium/appengine/common/triciumtest"
)

func TestFeedback(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()
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
		// AnalyzeRequest>WorkflowRun>FunctionRun>WorkerRun>Comment>CommentFeedback
		stime := tc.Now().UTC().Add(3 * time.Minute)
		etime := tc.Now().UTC().Add(7 * time.Minute)
		ctime1 := tc.Now().UTC().Add(2 * time.Minute) // before stime
		ctime2 := tc.Now().UTC().Add(4 * time.Minute) // between stime and etime
		ctx, _ = testclock.UseTime(ctx, now.Add(10*time.Minute))
		commentID1 := "7ef59cda-183c-48b3-8343-d9036a7f1419"
		commentID2 := "9400f12d-b425-4cf6-85d5-5636fc4e55a4"
		functionName := "Spacey"
		category1 := "Spacey/MixedSpace"
		category2 := "Spacey/TrailingSpace"
		platform := tricium.Platform_UBUNTU
		request := &track.AnalyzeRequest{}
		So(ds.Put(ctx, request), ShouldBeNil)
		run := &track.WorkflowRun{ID: 1, Parent: ds.KeyForObj(ctx, request)}
		So(ds.Put(ctx, run), ShouldBeNil)
		functionRun := &track.FunctionRun{ID: functionName, Parent: ds.KeyForObj(ctx, run)}
		So(ds.Put(ctx, functionRun), ShouldBeNil)
		worker := &track.WorkerRun{
			ID:     fmt.Sprintf("%s_%s", functionName, platform),
			Parent: ds.KeyForObj(ctx, functionRun),
		}
		So(ds.Put(ctx, worker), ShouldBeNil)
		comment1 := &track.Comment{
			UUID:         commentID1,
			Parent:       ds.KeyForObj(ctx, worker),
			Platforms:    1,
			Analyzer:     functionName,
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
			Analyzer:     functionName,
			Category:     category2,
			CreationTime: ctime2,
		}
		So(ds.Put(ctx, comment2), ShouldBeNil)
		feedback2 := &track.CommentFeedback{
			ID:               1,
			Parent:           ds.KeyForObj(ctx, comment2),
			NotUsefulReports: 1,
		}
		So(ds.Put(ctx, feedback2), ShouldBeNil)
		selection2 := &track.CommentSelection{
			ID:       1,
			Parent:   ds.KeyForObj(ctx, comment2),
			Included: true,
		}
		So(ds.Put(ctx, selection2), ShouldBeNil)

		Convey("Feedback request for unknown category", func() {
			st, et, _ := parseTimeRange(ctx, nil, nil)
			count, reports, err := feedback(ctx, "Hello", st, et)
			So(err, ShouldBeNil)
			So(count, ShouldEqual, 0)
			So(reports, ShouldEqual, 0)
		})

		Convey("Feedback request for known analyzer name", func() {
			st, et, _ := parseTimeRange(ctx, nil, nil)
			count, reports, err := feedback(ctx, functionName, st, et)
			So(err, ShouldBeNil)
			So(count, ShouldEqual, 2)
			So(reports, ShouldEqual, 3)
		})

		Convey("Feedback request for time period", func() {
			count, reports, err := feedback(ctx, functionName, stime, etime)
			So(err, ShouldBeNil)
			So(count, ShouldEqual, 1)
			So(reports, ShouldEqual, 1)
		})

		Convey("Feedback request for subcategory", func() {
			st, et, _ := parseTimeRange(ctx, nil, nil)
			count, reports, err := feedback(ctx, category1, st, et)
			So(err, ShouldBeNil)
			So(count, ShouldEqual, 1)
			So(reports, ShouldEqual, 2)
		})
	})
}

func TestParseTimeRange(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()
		epoch := time.Unix(0, 0).UTC()
		now := time.Date(2017, 1, 1, 0, 0, 0, 0, time.UTC)
		ctx, _ = testclock.UseTime(ctx, now)

		Convey("No start or end specified", func() {
			st, et, err := parseTimeRange(ctx, nil, nil)
			So(st, ShouldEqual, epoch)
			So(et, ShouldEqual, now)
			So(err, ShouldBeNil)
		})

		Convey("Both start and end time specified", func() {
			start := time.Date(2016, 11, 5, 0, 0, 0, 0, time.UTC)
			end := time.Date(2016, 11, 8, 0, 0, 0, 0, time.UTC)
			startTimestamp, err := ptypes.TimestampProto(start)
			So(err, ShouldBeNil)
			endTimestamp, err := ptypes.TimestampProto(end)
			So(err, ShouldBeNil)
			st, et, err := parseTimeRange(ctx, startTimestamp, endTimestamp)
			So(err, ShouldBeNil)
			So(st, ShouldEqual, start)
			So(et, ShouldEqual, end)
		})

		Convey("Reversed time", func() {
			start := time.Date(2016, 11, 8, 0, 0, 0, 0, time.UTC)
			end := time.Date(2016, 11, 5, 0, 0, 0, 0, time.UTC)
			startTimestamp, err := ptypes.TimestampProto(start)
			So(err, ShouldBeNil)
			endTimestamp, err := ptypes.TimestampProto(end)
			So(err, ShouldBeNil)
			_, _, err = parseTimeRange(ctx, startTimestamp, endTimestamp)
			So(err, ShouldNotBeNil)
		})
	})
}
