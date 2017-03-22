// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestDataRetrieved(t *testing.T) {

	s := ChopsService{}
	Convey("Use Convey/So", t, func() {

		s.Name = "testService"
		s.SLA = "www.google.com"
		So(s.Name, ShouldEqual, "testService")
		So(s.SLA, ShouldEqual, "www.google.com")
	})
}
