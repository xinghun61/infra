// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"encoding/json"
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

func TestResults(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		// Add run->analyzer->worker->comments
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
		json, err := json.Marshal(tricium.Data_Comment{
			Category: analyzerName,
			Message:  "Hello",
		})
		So(err, ShouldBeNil)
		comments := []*track.ResultComment{
			{
				Parent:    ds.KeyForObj(ctx, worker),
				Category:  analyzerName,
				Comment:   string(json),
				Platforms: 0,
				Included:  true,
			},
			{
				Parent:    ds.KeyForObj(ctx, worker),
				Category:  analyzerName,
				Comment:   string(json),
				Platforms: 0,
				Included:  false,
			},
		}
		err = ds.Put(ctx, comments)
		So(err, ShouldBeNil)

		Convey("Merged results request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})

			results, isMerged, err := results(ctx, run.ID)
			So(err, ShouldBeNil)
			So(len(results.Comments), ShouldEqual, 1)
			So(isMerged, ShouldBeTrue)
			comment := results.Comments[0]
			So(comment.Category, ShouldEqual, analyzerName)
		})
	})
}
