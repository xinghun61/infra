// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"encoding/json"
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"

	"infra/tricium/api/admin/v1"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

func TestReportResultsRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		analyzerName := "Lint"

		request := &track.AnalyzeRequest{
			GitRepo: "https://chromium-review.googlesource.com",
			GitRef:  "refs/changes/88/508788/1",
		}
		So(ds.Put(ctx, request), ShouldBeNil)
		requestKey := ds.KeyForObj(ctx, request)
		run := &track.WorkflowRun{ID: 1, Parent: requestKey}
		So(ds.Put(ctx, run), ShouldBeNil)
		runKey := ds.KeyForObj(ctx, run)
		So(ds.Put(ctx, &track.AnalyzerRun{
			ID:     analyzerName,
			Parent: runKey,
		}), ShouldBeNil)
		analyzerKey := ds.NewKey(ctx, "AnalyzerRun", analyzerName, 0, runKey)
		So(ds.Put(ctx, &track.AnalyzerRunResult{
			ID:          1,
			Parent:      analyzerKey,
			Name:        analyzerName,
			NumComments: 2,
		}), ShouldBeNil)
		workerName := analyzerName + "_UBUNTU"
		So(ds.Put(ctx, &track.WorkerRun{
			ID:     workerName,
			Parent: analyzerKey,
		}), ShouldBeNil)
		workerKey := ds.NewKey(ctx, "WorkerRun", workerName, 0, analyzerKey)
		json1, err := json.Marshal(fmt.Sprintf("{\"category\": %s,\"message\":\"Line too long\"}", analyzerName))
		So(err, ShouldBeNil)
		json2, err := json.Marshal(fmt.Sprintf("{\"category\": %s,\"message\":\"Line too short\"}", analyzerName))
		So(err, ShouldBeNil)
		results := []*track.Comment{
			{
				Parent:  workerKey,
				Comment: json1,
			},
			{
				Parent:  workerKey,
				Comment: json2,
			},
			{
				Parent:  workerKey,
				Comment: json2,
			},
		}
		So(ds.Put(ctx, results), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{ID: 1, Parent: ds.KeyForObj(ctx, results[0]), Included: true}), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{ID: 1, Parent: ds.KeyForObj(ctx, results[1]), Included: true}), ShouldBeNil)
		So(ds.Put(ctx, &track.CommentSelection{ID: 1, Parent: ds.KeyForObj(ctx, results[2]), Included: false}), ShouldBeNil)

		Convey("Report results request", func() {
			mock := &mockRestAPI{}
			err := reportResults(ctx, &admin.ReportResultsRequest{
				RunId:    run.ID,
				Analyzer: analyzerName,
			}, mock)
			So(err, ShouldBeNil)
			So(len(mock.LastComments), ShouldEqual, len(results)-1) // only include the two selected comments
		})
	})
}
