// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"google.golang.org/api/pubsub/v1"

	trit "infra/tricium/appengine/common/testing"
)

func TestDeocdePubsubMessage(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		Convey("Decodes pubsub message without error", func() {
			msg := &pubsub.PubsubMessage{
				MessageId:   "58708071417623",
				PublishTime: "2017-02-28T19:39:28.104Z",
				Data:        "eyJ0YXNrX2lkIjoiMzQ5ZjBkODQ5MjI3Y2QxMCIsInVzZXJkYXRhIjoiQ0lDQWdJQ0E2TjBLRWdkaFltTmxaR1puR2hoSVpXeHNiMTlWWW5WdWRIVXhOQzR3TkY5NE9EWXROalE9In0=",
			}
			_, _, err := decodePubsubMessage(ctx, msg)
			So(err, ShouldBeNil)
		})
	})
}
