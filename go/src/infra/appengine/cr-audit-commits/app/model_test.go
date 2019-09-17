// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestModel(t *testing.T) {
	t.Parallel()
	Convey("Test RelevantCommit.NotificationStates", t, func() {
		rc := &RelevantCommit{NotificationStates: []string{"ruleset1:value1"}}
		Convey("Accessor", func() {
			Convey("Key Missing", func() {
				So(rc.GetNotificationState("ruleset2"), ShouldEqual, "")
			})
			Convey("Key Present", func() {
				So(rc.GetNotificationState("ruleset1"), ShouldEqual, "value1")
			})
		})
		Convey("Mutator", func() {
			Convey("Key Missing", func() {
				rc.SetNotificationState("ruleset3", "value3")
				So(rc.NotificationStates, ShouldResemble, []string{
					"ruleset1:value1",
					"ruleset3:value3",
				})
			})
			Convey("Key Present", func() {
				rc.SetNotificationState("ruleset1", "value4")
				So(rc.NotificationStates, ShouldResemble, []string{"ruleset1:value4"})
			})
		})
	})
}
