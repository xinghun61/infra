// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"testing"

	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/authtest"
	"github.com/luci/luci-go/server/auth/identity"
	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/v1"
	trit "infra/tricium/appengine/common/testing"
)

func TestProgress(t *testing.T) {
	Convey("Test Environment", t, func() {

		tt := &trit.Testing{}
		ctx := tt.Context()

		Convey("Progress request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})

			_, err := progress(ctx, &tricium.ProgressRequest{RunId: "687463287432687"})
			So(err, ShouldBeNil)
		})
	})
}
