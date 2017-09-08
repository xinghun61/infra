// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"

	"google.golang.org/api/pubsub/v1"

	"infra/tricium/appengine/common"
	trit "infra/tricium/appengine/common/testing"
)

var (
	msg = &pubsub.PubsubMessage{
		MessageId:   "58708071417623",
		PublishTime: "2017-02-28T19:39:28.104Z",
		Data:        "eyJ0YXNrX2lkIjoiMzQ5ZjBkODQ5MjI3Y2QxMCIsInVzZXJkYXRhIjoiQ0lDQWdJQ0E2TjBLRWdkaFltTmxaR1puR2hoSVpXeHNiMTlWWW5WdWRIVXhOQzR3TkY5NE9EWXROalE9In0=",
	}
	taskID = "349f0d849227cd10" // matches the above pubsub message
)

func TestDeocdePubsubMessage(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()
		Convey("Decodes pubsub message without error", func() {
			_, _, err := decodePubsubMessage(ctx, msg)
			So(err, ShouldBeNil)
		})
	})
}

func TestHandlePubSubMessage(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()
		Convey("Enqueues collect task", func() {
			So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 0)
			received := &ReceivedPubSubMessage{ID: taskID}
			So(ds.Get(ctx, received), ShouldEqual, ds.ErrNoSuchEntity)
			err := handlePubSubMessage(ctx, msg)
			So(err, ShouldBeNil)
			So(ds.Get(ctx, received), ShouldBeNil)
			So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 1)
		})
		Convey("Avoids duplicate processing", func() {
			So(handlePubSubMessage(ctx, msg), ShouldBeNil)
			So(handlePubSubMessage(ctx, msg), ShouldBeNil)
			So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 1)
		})
	})
}
