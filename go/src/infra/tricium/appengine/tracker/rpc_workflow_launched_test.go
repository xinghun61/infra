// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"testing"

	"golang.org/x/net/context"

	ds "github.com/luci/gae/service/datastore"

	. "github.com/smartystreets/goconvey/convey"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

const (
	clangIsolatorUbuntu  = "ClangIsolator_Ubuntu14.04-x86-64"
	clangIsolatorWindows = "ClangIsolator_Windows-7-SP1-x86-64"
	fileIsolator         = "GitFileIsolator_Ubuntu14.04-x86-64"
)

// mockWorkflowProvider mocks common.WorkflowProvider.
type mockWorkflowProvider struct {
}

func (mockWorkflowProvider) ReadWorkflowForRun(c context.Context, runID int64) (*admin.Workflow, error) {
	return &admin.Workflow{
		Workers: []*admin.Worker{
			{
				Name:  clangIsolatorUbuntu,
				Needs: tricium.Data_FILES,
			},
			{
				Name:  clangIsolatorWindows,
				Needs: tricium.Data_FILES,
			},
			{
				Name:  fileIsolator,
				Needs: tricium.Data_GIT_FILE_DETAILS,
				Next: []string{
					clangIsolatorUbuntu,
					clangIsolatorWindows,
				},
			},
		},
	}, nil
}

func TestWorkflowLaunchedRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		Convey("Workflow request", func() {
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
			}, mockWorkflowProvider{})
			So(err, ShouldBeNil)

			Convey("Marks run as launched", func() {
				// Run entry is marked as launched.
				err = ds.Get(ctx, run)
				So(err, ShouldBeNil)
				So(run.State, ShouldEqual, track.Launched)
				// Worker and analyzer is marked pending.
				_, analyzerKey, workerKey := createKeys(ctx, runID, fileIsolator)
				w := &track.WorkerInvocation{
					ID:     workerKey.StringID(),
					Parent: workerKey.Parent(),
				}
				err = ds.Get(ctx, w)
				So(err, ShouldBeNil)
				So(w.State, ShouldEqual, track.Pending)
				a := &track.AnalyzerInvocation{
					ID:     analyzerKey.StringID(),
					Parent: analyzerKey.Parent(),
				}
				err = ds.Get(ctx, a)
				So(err, ShouldBeNil)
				So(a.State, ShouldEqual, track.Pending)
			})
		})
	})
}
