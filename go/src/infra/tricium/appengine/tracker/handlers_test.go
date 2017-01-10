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
	"infra/tricium/appengine/common/pipeline"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

type mockConfigProvider struct {
}

const (
	clangIsolatorUbuntu  = "ClangIsolator_Ubuntu14.04-x86-64"
	clangIsolatorWindows = "ClangIsolator_Windows-7-SP1-x86-64"
	fileIsolator         = "GitFileIsolator_Ubuntu14.04-x86-64"
)

func (*mockConfigProvider) readConfig(c context.Context, runID int64) (*admin.Workflow, error) {
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

func TestTrackRequest(t *testing.T) {
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
			tr := &pipeline.TrackRequest{
				RunID: runID,
				Kind:  pipeline.TrackWorkflowLaunched,
			}
			err = handleWorkflowLaunched(ctx, tr, &mockConfigProvider{})
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

			// Mark worker as launched.
			tr = &pipeline.TrackRequest{
				RunID:  runID,
				Kind:   pipeline.TrackWorkerLaunched,
				Worker: fileIsolator,
			}
			err = handleWorkerLaunched(ctx, tr)
			So(err, ShouldBeNil)

			Convey("Marks worker as launched", func() {
				_, analyzerKey, workerKey := createKeys(ctx, runID, tr.Worker)
				w := &track.WorkerInvocation{
					ID:     workerKey.StringID(),
					Parent: workerKey.Parent(),
				}
				err = ds.Get(ctx, w)
				So(err, ShouldBeNil)
				So(w.State, ShouldEqual, track.Launched)
				a := &track.AnalyzerInvocation{
					ID:     analyzerKey.StringID(),
					Parent: analyzerKey.Parent(),
				}
				err = ds.Get(ctx, a)
				So(err, ShouldBeNil)
				So(a.State, ShouldEqual, track.Launched)
			})

			// Mark worker as done.
			tr = &pipeline.TrackRequest{
				RunID:    runID,
				Kind:     pipeline.TrackWorkerDone,
				Worker:   fileIsolator,
				ExitCode: 0,
			}
			err = handleWorkerDone(ctx, tr)
			So(err, ShouldBeNil)

			Convey("Marks worker as done", func() {
				_, analyzerKey, workerKey := createKeys(ctx, runID, tr.Worker)
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
	})
}
