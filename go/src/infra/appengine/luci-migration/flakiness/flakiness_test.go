// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package flakiness

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/luci-go/common/api/buildbucket/buildbucket/v1"

	"github.com/luci/luci-go/common/errors"
	. "github.com/smartystreets/goconvey/convey"
)

func TestFlakiness(t *testing.T) {
	t.Parallel()

	Convey("Flakiness", t, func(testCtx C) {
		c := context.Background()
		c = memory.Use(c)

		// Mock buildbucket server.
		bbResponseCode := 0
		var actualBBRequest *buildbucket.ApiPutRequestMessage
		bbServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			actualBBRequest = &buildbucket.ApiPutRequestMessage{}
			err := json.NewDecoder(r.Body).Decode(actualBBRequest)
			testCtx.So(err, ShouldBeNil)

			if bbResponseCode != 0 {
				http.Error(w, "error", bbResponseCode)
				return
			}

			err = json.NewEncoder(w).Encode(&buildbucket.ApiBuildResponseMessage{
				Build: &buildbucket.ApiCommonBuildMessage{Id: 123456789},
			})
			testCtx.So(err, ShouldBeNil)
		}))
		defer bbServer.Close()
		bbService, err := buildbucket.New(&http.Client{})
		So(err, ShouldBeNil)
		bbService.BasePath = bbServer.URL

		const paramsExperimental = `{"properties": {"category": "cq_experimental"}}`

		Convey("retries builds", func() {
			b := &Build{
				ID:             "54",
				Bucket:         "luci.test.x",
				Result:         "FAILURE",
				ParametersJSON: paramsExperimental,
				Tags:           []string{"buildset:patchsetX", "master:masterX"},
			}
			err := HandleNotification(c, b, bbService)
			So(err, ShouldBeNil)

			So(actualBBRequest, ShouldResemble, &buildbucket.ApiPutRequestMessage{
				Bucket:            "luci.test.x",
				ClientOperationId: "luci-migration-retry-54",
				ParametersJson:    b.ParametersJSON,
				Tags: []string{
					"user_agent:luci-migration",
					formatTag(origBuildIDTagKey, "54"),
					formatTag(retryAttemptTagKey, "0"),
					"buildset:patchsetX",
					"master:masterX",
				},
			})
		})

		Convey("retries second time", func() {
			b := &Build{
				ID:             "54",
				Bucket:         "luci.test.x",
				Result:         "FAILURE",
				ParametersJSON: paramsExperimental,
				Tags: []string{
					formatTag(origBuildIDTagKey, "53"),
					formatTag(retryAttemptTagKey, "0"),
				},
			}
			err := HandleNotification(c, b, bbService)
			So(err, ShouldBeNil)
			So(actualBBRequest, ShouldNotBeNil) // did retry
			So(formatTag(origBuildIDTagKey, "53"), ShouldBeIn, actualBBRequest.Tags)
		})

		Convey("does not retry too many times", func() {
			b := &Build{
				ID:             "54",
				Bucket:         "luci.test.x",
				Result:         "FAILURE",
				ParametersJSON: paramsExperimental,
				Tags: []string{
					formatTag(origBuildIDTagKey, "53"),
					formatTag(retryAttemptTagKey, "1"),
				},
			}
			err := HandleNotification(c, b, bbService)
			So(err, ShouldBeNil)
			So(actualBBRequest, ShouldBeNil) // did not retry
		})

		Convey("does not retry non-luci builds", func() {
			b := &Build{
				ID:             "54",
				Bucket:         "master.tryserver.chromium.linux",
				Result:         "FAILURE",
				ParametersJSON: paramsExperimental,
			}
			err := HandleNotification(c, b, bbService)
			So(err, ShouldBeNil)
			So(actualBBRequest, ShouldBeNil) // did not retry
		})

		Convey("does not retry non-failed builds", func() {
			b := &Build{
				ID:             "54",
				Bucket:         "master.tryserver.chromium.linux",
				Result:         "SUCCESS",
				ParametersJSON: paramsExperimental,
			}
			err := HandleNotification(c, b, bbService)
			So(err, ShouldBeNil)
			So(actualBBRequest, ShouldBeNil) // did not retry
		})

		Convey("does not retry non-experimental builds", func() {
			b := &Build{
				ID:     "54",
				Bucket: "master.tryserver.chromium.linux",
				Result: "SUCCESS",
			}
			err := HandleNotification(c, b, bbService)
			So(err, ShouldBeNil)
			So(actualBBRequest, ShouldBeNil) // did not retry
		})

		Convey("returns transient error on Buildbucket HTTP 500", func() {
			b := &Build{
				ID:             "54",
				Bucket:         "luci.test.x",
				Result:         "FAILURE",
				ParametersJSON: paramsExperimental,
				Tags:           []string{"buildset:patchsetX", "master:masterX"},
			}
			bbResponseCode = 500
			err := HandleNotification(c, b, bbService)
			So(err, ShouldNotBeNil)
			So(errors.IsTransient(err), ShouldBeTrue)
		})

		Convey("returns non-transient error on Buildbucket HTTP 403", func() {
			b := &Build{
				ID:             "54",
				Bucket:         "luci.test.x",
				Result:         "FAILURE",
				ParametersJSON: paramsExperimental,
				Tags:           []string{"buildset:patchsetX", "master:masterX"},
			}
			bbResponseCode = 403
			err := HandleNotification(c, b, bbService)
			So(err, ShouldNotBeNil)
			So(errors.IsTransient(err), ShouldBeFalse)
		})

		Convey("returns non-transient error on Buildbucket HTTP 404", func() {
			b := &Build{
				ID:             "54",
				Bucket:         "luci.test.x",
				Result:         "FAILURE",
				ParametersJSON: paramsExperimental,
				Tags:           []string{"buildset:patchsetX", "master:masterX"},
			}
			bbResponseCode = 404
			err := HandleNotification(c, b, bbService)
			So(err, ShouldNotBeNil)
			So(errors.IsTransient(err), ShouldBeFalse)
		})
	})
}
