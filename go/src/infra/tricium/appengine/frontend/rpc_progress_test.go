// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"testing"

	ds "github.com/luci/gae/service/datastore"

	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/authtest"
	"github.com/luci/luci-go/server/auth/identity"
	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/v1"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

func TestProgress(t *testing.T) {
	Convey("Test Environment", t, func() {

		tt := &trit.Testing{}
		ctx := tt.Context()

		// Add completed run entry.
		run := &track.Run{
			State: tricium.State_SUCCESS,
		}
		err := ds.Put(ctx, run)
		So(err, ShouldBeNil)
		analyzerName := "Hello"
		platform := tricium.Platform_UBUNTU
		analyzer := &track.AnalyzerInvocation{
			Name:  analyzerName,
			State: tricium.State_SUCCESS,
		}
		analyzer.Parent = ds.KeyForObj(ctx, run)
		err = ds.Put(ctx, analyzer)
		So(err, ShouldBeNil)
		worker := &track.WorkerInvocation{
			Name:              analyzerName + "_UBUNTU",
			State:             tricium.State_SUCCESS,
			NumResultComments: 1,
			Platform:          platform,
		}
		worker.Parent = ds.KeyForObj(ctx, analyzer)
		err = ds.Put(ctx, worker)
		So(err, ShouldBeNil)

		Convey("Progress request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})

			state, progress, err := progress(ctx, run.ID)
			So(err, ShouldBeNil)
			So(state, ShouldEqual, tricium.State_SUCCESS)
			So(len(progress), ShouldEqual, 1)
			So(progress[0].Analyzer, ShouldEqual, analyzerName)
			So(progress[0].Platform, ShouldEqual, platform)
			So(progress[0].NumResultComments, ShouldEqual, 1)
			So(progress[0].State, ShouldEqual, tricium.State_SUCCESS)
		})
	})
}
