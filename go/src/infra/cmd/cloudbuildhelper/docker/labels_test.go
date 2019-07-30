// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package docker

import (
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
)

func TestLabels(t *testing.T) {
	t.Parallel()

	Convey("Empty", t, func() {
		l := Labels{}
		So(l.AsBuildArgs(), ShouldHaveLength, 0)
	})

	Convey("Non-empty", t, func() {
		l := Labels{
			Created:      time.Date(2016, time.February, 3, 4, 5, 6, 7, time.UTC),
			BuildTool:    "xxx",
			BuildMode:    "yyy",
			Inputs:       "zzz",
			BuildID:      "123",
			CanonicalTag: "www",
			Extra: map[string]string{
				"k1":                      "v1",
				"org.chromium.build.tool": "should be overridden",
			},
		}
		So(l.AsBuildArgs(), ShouldResemble, []string{
			"--label", "k1=v1",
			"--label", "org.chromium.build.canonical=www",
			"--label", "org.chromium.build.id=123",
			"--label", "org.chromium.build.inputs=zzz",
			"--label", "org.chromium.build.mode=yyy",
			"--label", "org.chromium.build.tool=xxx",
			"--label", "org.opencontainers.image.created=2016-02-03T04:05:06Z",
		})
	})
}
