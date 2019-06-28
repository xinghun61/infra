// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io/ioutil"
	"net/http/httptest"
	"testing"

	"github.com/golang/protobuf/proto"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/triciumtest"
)

func TestMainPageHandler(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()
		authState := &authtest.FakeState{
			Identity: "user:user@example.com",
		}
		ctx = auth.WithState(ctx, authState)
		w := httptest.NewRecorder()

		Convey("Basic request to main page handler", func() {
			mainPageHandler(&router.Context{
				Context: ctx,
				Writer:  w,
				Request: triciumtest.MakeGetRequest(nil),
				Params:  triciumtest.MakeParams(),
			})
			So(w.Code, ShouldEqual, 200)
			r, err := ioutil.ReadAll(w.Body)
			So(err, ShouldBeNil)
			body := string(r)
			So(body, ShouldContainSubstring, "html")
		})

		Convey("Constructing template args", func() {
			args, err := templateArgs(ctx, triciumtest.MakeGetRequest(nil))
			So(err, ShouldBeNil)
			So(args, ShouldResemble, map[string]interface{}{
				"AppVersion":  "testVersionID",
				"IsAnonymous": false,
				"LoginURL":    "http://fake.example.com/login?dest=%2Ftesting-path",
				"LogoutURL":   "http://fake.example.com/logout?dest=%2Ftesting-path",
				"User":        "user@example.com",
			})
		})
	})
}

func TestAnalyzeQueueHandler(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()
		w := httptest.NewRecorder()

		Convey("Analyze queue handler checks for invalid requests", func() {
			// A request with an empty paths list is not valid.
			ar := &tricium.AnalyzeRequest{
				Project: "some-project",
				Files:   nil,
				Source: &tricium.AnalyzeRequest_GitCommit{
					GitCommit: &tricium.GitCommit{
						Ref: "some/ref",
						Url: "https://example.com/repo.git",
					},
				},
			}
			bytes, err := proto.Marshal(ar)
			analyzeHandler(&router.Context{
				Context: ctx,
				Writer:  w,
				Request: triciumtest.MakeGetRequest(bytes),
				Params:  triciumtest.MakeParams(),
			})
			So(w.Code, ShouldEqual, 400)
			r, err := ioutil.ReadAll(w.Body)
			So(err, ShouldBeNil)
			body := string(r)
			So(body, ShouldEqual, "")
		})
	})
}
