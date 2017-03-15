// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"testing"

	ds "github.com/luci/gae/service/datastore"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

func TestWorkerDoneRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		// Add pending run entry.
		run := &track.Run{
			State: track.Pending,
		}
		err := ds.Put(ctx, run)
		So(err, ShouldBeNil)

		runID := run.ID

		// Mark workflow as launched.
		err = workflowLaunched(ctx, &admin.WorkflowLaunchedRequest{
			RunId: runID,
		}, &mockConfigProvider{})
		So(err, ShouldBeNil)

		// Mark worker as launched.
		err = workerLaunched(ctx, &admin.WorkerLaunchedRequest{
			RunId:  runID,
			Worker: fileIsolator,
		})
		So(err, ShouldBeNil)

		// Mark worker as done.
		err = workerDone(ctx, &admin.WorkerDoneRequest{
			RunId:    runID,
			Worker:   fileIsolator,
			ExitCode: 0,
		}, &common.MockIsolator{})
		So(err, ShouldBeNil)

		Convey("Marks worker as done", func() {
			_, analyzerKey, workerKey := createKeys(ctx, runID, fileIsolator)
			w := &track.WorkerInvocation{
				ID:     workerKey.StringID(),
				Parent: workerKey.Parent(),
			}
			err = ds.Get(ctx, w)
			So(err, ShouldBeNil)
			So(w.State, ShouldEqual, track.DoneSuccess)
			a := &track.AnalyzerInvocation{
				ID:     analyzerKey.StringID(),
				Parent: analyzerKey.Parent(),
			}
			err = ds.Get(ctx, a)
			So(err, ShouldBeNil)
			So(a.State, ShouldEqual, track.DoneSuccess)
		})
		// TODO(emso): multi-platform analyzer is half done, analyzer stays launched
	})
}
