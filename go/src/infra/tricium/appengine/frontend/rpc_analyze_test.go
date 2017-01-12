// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"testing"

	tq "github.com/luci/gae/service/taskqueue"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	trit "infra/tricium/appengine/common/testing"
)

func TestAnalyzeRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		project := "test-project"
		gitref := "ref/test"
		paths := []string{
			"README.md",
			"README2.md",
		}

		Convey("Service request", func() {
			_, err := triciumServer.Analyze(ctx, &tricium.TriciumRequest{
				Project: project,
				GitRef:  gitref,
				Paths:   paths,
			})
			So(err, ShouldBeNil)

			Convey("Enqueues launch request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.LauncherQueue]), ShouldEqual, 1)
			})

			Convey("Adds tracking of run", func() {
				r, err := runs(ctx)
				So(err, ShouldBeNil)
				So(len(r), ShouldEqual, 1)
			})
		})
	})
}
