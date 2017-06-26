// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"fmt"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
)

func TestComposeChangesQueryURL(t *testing.T) {
	Convey("Test Environment", t, func() {
		instance := "https://chromium-review.googlesource.com"
		project := "playground/gerrit-tricium"
		formattedProject := "playground%2Fgerrit-tricium"
		const form = "2006-01-02 15:04:05.000000000"
		time, err := time.Parse(form, "2016-10-01 10:00:05.640000000")
		So(err, ShouldBeNil)
		formattedTime := "2016-10-01+10%3A00%3A05.640000000"
		Convey("First page of poll", func() {
			So(composeChangesQueryURL(instance, project, time, 0), ShouldEqual,
				fmt.Sprintf("%s/a/changes/?o=CURRENT_REVISION&o=CURRENT_FILES&q=project%%3A%s+after%%3A%%22%s%%22&start=0",
					instance, formattedProject, formattedTime))
		})
	})
}
