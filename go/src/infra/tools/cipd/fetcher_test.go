// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"io/ioutil"
	"net/url"
	"os"
	"path/filepath"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
)

func TestFetchInstance(t *testing.T) {
	Convey("Mocking remote service", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tempDir) })
		tempFile := filepath.Join(tempDir, "pkg")

		mockClock(time.Now())
		mockResumableUpload()

		Convey("FetchInstance full flow", func() {
			service := mockRemoteServiceWithExpectations([]expectedHTTPCall{
				expectedHTTPCall{
					Method: "GET",
					Path:   "/_ah/api/repo/v1/instance",
					Query: url.Values{
						"instance_id":  []string{"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
						"package_name": []string{"pkgname"},
					},
					Reply: `{
						"status": "SUCCESS",
						"instance": {
							"registered_by": "user:a@example.com",
							"registered_ts": "0"
						},
						"fetch_url": "http://localhost/fake_fetch_url"
					}`,
				},
				expectedHTTPCall{
					Method: "GET",
					Path:   "/fake_fetch_url",
					Status: 500,
					Reply:  "error",
				},
				expectedHTTPCall{
					Method: "GET",
					Path:   "/fake_fetch_url",
					Status: 200,
					Reply:  "package body data",
				},
			})

			out, err := os.OpenFile(tempFile, os.O_WRONLY|os.O_CREATE, 0666)
			So(err, ShouldBeNil)
			closed := false
			defer func() {
				if !closed {
					out.Close()
				}
			}()

			err = FetchInstance(FetchInstanceOptions{
				Client:      service.client,
				Output:      out,
				PackageName: "pkgname",
				InstanceID:  "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
			})
			So(err, ShouldBeNil)
			out.Close()
			closed = true

			body, err := ioutil.ReadFile(tempFile)
			So(err, ShouldBeNil)
			So(string(body), ShouldEqual, "package body data")
		})
	})
}
