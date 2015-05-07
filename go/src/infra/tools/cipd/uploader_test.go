// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"bytes"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"testing"
	"time"

	"infra/libs/logging"

	. "github.com/smartystreets/goconvey/convey"
)

func TestUploadToCAS(t *testing.T) {
	Convey("Given a mocked service and clock", t, func() {
		mockClock(time.Now())
		mockResumableUpload()

		Convey("UploadToCAS full flow", func() {
			mockRemoteServiceWithExpectations([]expectedHTTPCall{
				{
					Method: "POST",
					Path:   "/_ah/api/cas/v1/upload/SHA1/abc",
					Reply:  `{"status":"SUCCESS","upload_session_id":"12345","upload_url":"http://localhost"}`,
				},
				{
					Method: "POST",
					Path:   "/_ah/api/cas/v1/finalize/12345",
					Reply:  `{"status":"VERIFYING"}`,
				},
				{
					Method: "POST",
					Path:   "/_ah/api/cas/v1/finalize/12345",
					Reply:  `{"status":"PUBLISHED"}`,
				},
			})
			err := UploadToCAS(UploadToCASOptions{SHA1: "abc"})
			So(err, ShouldBeNil)
		})

		Convey("UploadToCAS timeout", func() {
			// Append a bunch of "still verifying" responses at the end.
			calls := []expectedHTTPCall{
				{
					Method: "POST",
					Path:   "/_ah/api/cas/v1/upload/SHA1/abc",
					Reply:  `{"status":"SUCCESS","upload_session_id":"12345","upload_url":"http://localhost"}`,
				},
			}
			for i := 0; i < 19; i++ {
				calls = append(calls, expectedHTTPCall{
					Method: "POST",
					Path:   "/_ah/api/cas/v1/finalize/12345",
					Reply:  `{"status":"VERIFYING"}`,
				})
			}
			mockRemoteServiceWithExpectations(calls)
			err := UploadToCAS(UploadToCASOptions{SHA1: "abc"})
			So(err, ShouldEqual, ErrFinalizationTimeout)
		})
	})
}

func TestRegisterInstance(t *testing.T) {
	Convey("Mocking remote service", t, func() {
		mockClock(time.Now())
		mockResumableUpload()

		// Build an empty package to be uploaded.
		out := bytes.Buffer{}
		err := BuildInstance(BuildInstanceOptions{
			Input:       []File{},
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Open it for reading.
		inst, err := OpenInstance(bytes.NewReader(out.Bytes()), "")
		So(err, ShouldBeNil)
		Reset(func() { inst.Close() })

		Convey("RegisterInstance full flow", func() {
			mockRemoteServiceWithExpectations([]expectedHTTPCall{
				{
					Method: "POST",
					Path:   "/_ah/api/repo/v1/instance",
					Query: url.Values{
						"instance_id":  []string{inst.InstanceID()},
						"package_name": []string{inst.PackageName()},
					},
					Reply: `{
						"status": "UPLOAD_FIRST",
						"upload_session_id": "12345",
						"upload_url": "http://localhost"
					}`,
				},
				{
					Method: "POST",
					Path:   "/_ah/api/cas/v1/finalize/12345",
					Reply:  `{"status":"PUBLISHED"}`,
				},
				{
					Method: "POST",
					Path:   "/_ah/api/repo/v1/instance",
					Query: url.Values{
						"instance_id":  []string{inst.InstanceID()},
						"package_name": []string{inst.PackageName()},
					},
					Reply: `{
						"status": "REGISTERED",
						"instance": {
							"registered_by": "user:a@example.com",
							"registered_ts": "0"
						}
					}`,
				},
			})
			err = RegisterInstance(RegisterInstanceOptions{PackageInstance: inst})
			So(err, ShouldBeNil)
		})

		Convey("RegisterInstance already registered", func() {
			mockRemoteServiceWithExpectations([]expectedHTTPCall{
				{
					Method: "POST",
					Path:   "/_ah/api/repo/v1/instance",
					Query: url.Values{
						"instance_id":  []string{inst.InstanceID()},
						"package_name": []string{inst.PackageName()},
					},
					Reply: `{
						"status": "ALREADY_REGISTERED",
						"instance": {
							"registered_by": "user:a@example.com",
							"registered_ts": "0"
						}
					}`,
				},
			})
			err = RegisterInstance(RegisterInstanceOptions{PackageInstance: inst})
			So(err, ShouldBeNil)
		})
	})
}

func TestResumableUpload(t *testing.T) {
	Convey("Resumable upload full flow", t, func(c C) {
		mockClock(time.Now())

		dataToUpload := "0123456789abcdef"
		totalLen := len(dataToUpload)
		uploaded := bytes.NewBuffer(nil)
		errors := 0

		server, client := mockServerWithHandler("/", func(w http.ResponseWriter, r *http.Request) {
			c.So(r.URL.Path, ShouldEqual, "/upl")
			c.So(r.Method, ShouldEqual, "PUT")

			rangeHeader := r.Header.Get("Content-Range")
			body, err := ioutil.ReadAll(r.Body)
			c.So(err, ShouldBeNil)

			// Insert a bunch of consecutive transient errors in the middle.
			cur := uploaded.Len()
			if cur > totalLen/2 && errors < 3 {
				errors++
				w.WriteHeader(500)
				return
			}

			// Request for uploaded offset.
			if len(body) == 0 {
				c.So(rangeHeader, ShouldEqual, fmt.Sprintf("bytes */%d", totalLen))
				if cur == totalLen {
					w.WriteHeader(200)
					return
				}
				if cur != 0 {
					w.Header().Set("Range", fmt.Sprintf("bytes=0-%d", cur-1))
				}
				w.WriteHeader(308)
				return
			}

			// Uploading next chunk.
			c.So(rangeHeader, ShouldEqual, fmt.Sprintf("bytes %d-%d/%d", cur, cur+len(body)-1, totalLen))
			_, err = uploaded.Write(body)
			c.So(err, ShouldBeNil)
			if uploaded.Len() == totalLen {
				w.WriteHeader(200)
			} else {
				w.WriteHeader(308)
			}
		})

		err := resumableUpload(server.URL+"/upl", 3, UploadToCASOptions{
			SHA1: "abc",
			Data: bytes.NewReader([]byte(dataToUpload)),
			UploadOptions: UploadOptions{
				Client: client,
				Log:    logging.DefaultLogger,
			},
		})
		So(err, ShouldBeNil)
		So(uploaded.Bytes(), ShouldResemble, []byte(dataToUpload))
	})
}

func TestAttachTagsWhenReady(t *testing.T) {
	Convey("Mocking clock", t, func() {
		mockClock(time.Now())

		Convey("attachTagsWhenReady works", func() {
			remote := mockRemoteServiceWithExpectations([]expectedHTTPCall{
				{
					Method: "POST",
					Path:   "/_ah/api/repo/v1/tags",
					Query: url.Values{
						"instance_id":  []string{"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
						"package_name": []string{"pkgname"},
					},
					Reply: `{"status": "PROCESSING_NOT_FINISHED_YET"}`,
				},
				{
					Method: "POST",
					Path:   "/_ah/api/repo/v1/tags",
					Query: url.Values{
						"instance_id":  []string{"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
						"package_name": []string{"pkgname"},
					},
					Reply: `{"status": "SUCCESS"}`,
				},
			})
			err := attachTagsWhenReady(
				remote, "pkgname", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
				[]string{"tag1:value1"}, logging.DefaultLogger)
			So(err, ShouldBeNil)
		})

		Convey("attachTagsWhenReady timeout", func() {
			calls := []expectedHTTPCall{}
			for i := 0; i < 20; i++ {
				calls = append(calls, expectedHTTPCall{
					Method: "POST",
					Path:   "/_ah/api/repo/v1/tags",
					Query: url.Values{
						"instance_id":  []string{"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
						"package_name": []string{"pkgname"},
					},
					Reply: `{"status": "PROCESSING_NOT_FINISHED_YET"}`,
				})
			}
			remote := mockRemoteServiceWithExpectations(calls)
			err := attachTagsWhenReady(
				remote, "pkgname", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
				[]string{"tag1:value1"}, logging.DefaultLogger)
			So(err, ShouldEqual, ErrAttachTagsTimeout)
		})
	})
}

func mockResumableUpload() {
	prev := resumableUpload
	resumableUpload = func(string, int64, UploadToCASOptions) error {
		return nil
	}
	Reset(func() { resumableUpload = prev })
}
