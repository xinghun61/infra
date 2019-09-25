// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package step

import (
	"encoding/json"
	"net/url"
	"testing"
	"time"

	"golang.org/x/net/context"

	testhelper "infra/appengine/sheriff-o-matic/som/client/test"
	te "infra/appengine/sheriff-o-matic/som/testexpectations"
	"infra/monitoring/messages"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/gae/service/urlfetch"

	. "github.com/smartystreets/goconvey/convey"
)

type giMock struct {
	info.RawInterface
	token  string
	expiry time.Time
	err    error
}

func (gi giMock) AccessToken(scopes ...string) (token string, expiry time.Time, err error) {
	return gi.token, gi.expiry, gi.err
}

func setUpGitiles(c context.Context) context.Context {
	data, _ := json.Marshal(map[string]*te.BuilderConfig{})

	return urlfetch.Set(c, &testhelper.MockGitilesTransport{
		Responses: map[string]string{
			"https://chromium.googlesource.com/chromium/src/+/master/third_party/blink/tools/blinkpy/common/config/builders.json?format=TEXT": string(data),
		},
	})
}

func TestTruncateTestName(t *testing.T) {
	Convey("testTrunc", t, func() {
		t := &TestFailure{
			TestNames: []string{"hi"},
		}

		Convey("basic", func() {
			So(t.testTrunc(), ShouldResemble, "hi")
		})

		Convey("multiple tests", func() {
			t.TestNames = []string{"a", "b"}
			So(t.testTrunc(), ShouldResemble, "a and 1 other(s)")
		})

		Convey("chromium tree example", func() {
			t.TestNames = []string{"virtual/outofblink-cors/http/tests/xmlhttprequest/redirect-cross-origin-post.html"}
			So(t.testTrunc(), ShouldResemble, "virtual/.../redirect-cross-origin-post.html")
		})

		Convey("chromium.perf tree example", func() {
			t.TestNames = []string{"smoothness.top_25_smooth/https://plus.google.com/110031535020051778989/posts"}
			So(t.testTrunc(), ShouldResemble, "smoothness.top_25_smooth/https://plus.google.com/110031535020051778989/posts")
		})
	})
}

func TestGetTestSuite(t *testing.T) {
	Convey("GetTestSuite", t, func() {
		s := &messages.BuildStep{
			Step: &messages.Step{
				Name: "thing_tests",
			},
		}
		url, err := url.Parse("https://build.chromium.org/p/chromium.linux")
		So(err, ShouldBeNil)
		s.Master = &messages.MasterLocation{
			URL: *url,
		}
		Convey("basic", func() {
			So(GetTestSuite(s), ShouldEqual, "thing_tests")
		})
		Convey("with suffixes", func() {
			s.Step.Name = "thing_tests on Intel GPU on Linux"
			So(GetTestSuite(s), ShouldEqual, "thing_tests")
		})
		Convey("on perf", func() {
			url, err = url.Parse("https://build.chromium.org/p/chromium.perf")
			So(err, ShouldBeNil)
			s.Master = &messages.MasterLocation{
				URL: *url,
			}
			s.Step.Logs = [][]interface{}{
				{
					"chromium_swarming.summary",
					"foo",
				},
			}
			Convey("with suffixes", func() {
				s.Step.Name = "battor.power_cases on Intel GPU on Linux"
				So(GetTestSuite(s), ShouldEqual, "battor.power_cases")
			})
			Convey("C++ test with suffixes", func() {
				s.Step.Name = "performance_browser_tests on Intel GPU on Linux"
				So(GetTestSuite(s), ShouldEqual, "performance_browser_tests")
			})
			Convey("not a test", func() {
				s.Step.Logs = nil
				s.Step.Name = "something_random"
				So(GetTestSuite(s), ShouldEqual, "")
			})
		})
	})
}
