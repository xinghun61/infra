// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"bytes"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

	"infra/libs/logging"

	. "github.com/smartystreets/goconvey/convey"
)

func TestRemoteService(t *testing.T) {
	mockInitiateUpload := func(response string) (*uploadSession, error) {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			So(r.URL.Path, ShouldEqual, "/_ah/api/cas/v1/upload/SHA1/abc")
			w.Write([]byte(response))
		})
		return remote.initiateUpload("abc")
	}

	mockFinalizeUpload := func(response string) (bool, error) {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			So(r.URL.Path, ShouldEqual, "/_ah/api/cas/v1/finalize/abc")
			w.Write([]byte(response))
		})
		return remote.finalizeUpload("abc")
	}

	Convey("makeRequest works", t, func() {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			So(r.Method, ShouldEqual, "POST")
			So(r.URL.Path, ShouldEqual, "/_ah/api/cas/v1/method")
			w.Write([]byte(`{"value":"123"}`))
		})
		var reply struct {
			Value string `json:"value"`
		}
		err := remote.makeRequest("cas/v1/method", &reply)
		So(err, ShouldBeNil)
		So(reply.Value, ShouldEqual, "123")
	})

	Convey("makeRequest handles fatal error", t, func() {
		calls := 0
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			calls++
			w.WriteHeader(403)
		})
		var reply struct{}
		err := remote.makeRequest("cas/v1/method", &reply)
		So(err, ShouldNotBeNil)
		So(calls, ShouldEqual, 1)
	})

	Convey("makeRequest handles retries", t, func() {
		mockClock(time.Now())
		calls := 0
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			calls++
			if calls == 1 {
				w.WriteHeader(500)
			} else {
				w.Write([]byte(`{}`))
			}
		})
		var reply struct{}
		err := remote.makeRequest("cas/v1/method", &reply)
		So(err, ShouldBeNil)
		So(calls, ShouldEqual, 2)
	})

	Convey("makeRequest gives up trying", t, func() {
		mockClock(time.Now())
		calls := 0
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			calls++
			w.WriteHeader(500)
		})
		var reply struct{}
		err := remote.makeRequest("cas/v1/method", &reply)
		So(err, ShouldNotBeNil)
		So(calls, ShouldEqual, 10)
	})

	Convey("initiateUpload ALREADY_UPLOADED", t, func() {
		s, err := mockInitiateUpload(`{"status":"ALREADY_UPLOADED"}`)
		So(err, ShouldBeNil)
		So(s, ShouldBeNil)
	})

	Convey("initiateUpload SUCCESS", t, func() {
		s, err := mockInitiateUpload(`{"status":"SUCCESS","upload_session_id":"123","upload_url":"http://localhost"}`)
		So(err, ShouldBeNil)
		So(s, ShouldResemble, &uploadSession{
			ID:  "123",
			URL: "http://localhost",
		})
	})

	Convey("initiateUpload ERROR", t, func() {
		s, err := mockInitiateUpload(`{"status":"ERROR","error_message":"boo"}`)
		So(err, ShouldNotBeNil)
		So(s, ShouldBeNil)
	})

	Convey("initiateUpload unknown status", t, func() {
		s, err := mockInitiateUpload(`{"status":"???"}`)
		So(err, ShouldNotBeNil)
		So(s, ShouldBeNil)
	})

	Convey("initiateUpload bad reply", t, func() {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			So(r.URL.Path, ShouldEqual, "/_ah/api/cas/v1/upload/SHA1/abc")
			w.WriteHeader(403)
		})
		s, err := remote.initiateUpload("abc")
		So(err, ShouldNotBeNil)
		So(s, ShouldBeNil)
	})

	Convey("finalizeUpload MISSING", t, func() {
		finished, err := mockFinalizeUpload(`{"status":"MISSING"}`)
		So(err, ShouldNotBeNil)
		So(finished, ShouldBeFalse)
	})

	Convey("finalizeUpload UPLOADING", t, func() {
		finished, err := mockFinalizeUpload(`{"status":"UPLOADING"}`)
		So(err, ShouldBeNil)
		So(finished, ShouldBeFalse)
	})

	Convey("finalizeUpload VERIFYING", t, func() {
		finished, err := mockFinalizeUpload(`{"status":"VERIFYING"}`)
		So(err, ShouldBeNil)
		So(finished, ShouldBeFalse)
	})

	Convey("finalizeUpload PUBLISHED", t, func() {
		finished, err := mockFinalizeUpload(`{"status":"PUBLISHED"}`)
		So(err, ShouldBeNil)
		So(finished, ShouldBeTrue)
	})

	Convey("finalizeUpload ERROR", t, func() {
		finished, err := mockFinalizeUpload(`{"status":"ERROR","error_message":"boo"}`)
		So(err, ShouldNotBeNil)
		So(finished, ShouldBeFalse)
	})

	Convey("finalizeUpload unknown status", t, func() {
		finished, err := mockFinalizeUpload(`{"status":"???"}`)
		So(err, ShouldNotBeNil)
		So(finished, ShouldBeFalse)
	})

	Convey("finalizeUpload bad reply", t, func() {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			So(r.URL.Path, ShouldEqual, "/_ah/api/cas/v1/finalize/abc")
			w.WriteHeader(403)
		})
		finished, err := remote.finalizeUpload("abc")
		So(err, ShouldNotBeNil)
		So(finished, ShouldBeFalse)
	})
}

func TestUploadToCAS(t *testing.T) {
	Convey("Given a mocked service and clock", t, func() {
		finalizeCalls := 0
		finalizeCallsToPublish := 5
		mockClock(time.Now())
		mockResumableUpload()
		mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path == "/_ah/api/cas/v1/upload/SHA1/abc" {
				resp := `{"status":"SUCCESS","upload_session_id":"12345","upload_url":"http://localhost"}`
				w.Write([]byte(resp))
			} else if r.URL.Path == "/_ah/api/cas/v1/finalize/12345" {
				finalizeCalls++
				if finalizeCalls == finalizeCallsToPublish {
					w.Write([]byte(`{"status":"PUBLISHED"}`))
				} else {
					w.Write([]byte(`{"status":"VERIFYING"}`))
				}
			} else {
				t.Errorf("Unexpected URL call: %s", r.URL.Path)
			}
		})

		Convey("UploadToCAS full flow", func() {
			err := UploadToCAS(UploadToCASOptions{SHA1: "abc"})
			So(err, ShouldBeNil)
		})

		Convey("UploadToCAS timeout", func() {
			finalizeCallsToPublish = -1
			err := UploadToCAS(UploadToCASOptions{SHA1: "abc"})
			So(err, ShouldEqual, ErrFinalizationTimeout)
		})
	})
}

func TestResumableUpload(t *testing.T) {
	Convey("Resumable upload full flow", t, func() {
		mockClock(time.Now())

		dataToUpload := "0123456789abcdef"
		totalLen := len(dataToUpload)
		uploaded := bytes.NewBuffer(nil)
		errors := 0

		server, client := mockServerWithHandler("/", func(w http.ResponseWriter, r *http.Request) {
			So(r.URL.Path, ShouldEqual, "/upl")
			So(r.Method, ShouldEqual, "PUT")

			rangeHeader := r.Header.Get("Content-Range")
			body, err := ioutil.ReadAll(r.Body)
			So(err, ShouldBeNil)

			// Insert a bunch of consecutive transient errors in the middle.
			cur := uploaded.Len()
			if cur > totalLen/2 && errors < 3 {
				errors++
				w.WriteHeader(500)
				return
			}

			// Request for uploaded offset.
			if len(body) == 0 {
				So(rangeHeader, ShouldEqual, fmt.Sprintf("bytes */%d", totalLen))
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
			So(rangeHeader, ShouldEqual, fmt.Sprintf("bytes %d-%d/%d", cur, cur+len(body)-1, totalLen))
			_, err = uploaded.Write(body)
			So(err, ShouldBeNil)
			if uploaded.Len() == totalLen {
				w.WriteHeader(200)
			} else {
				w.WriteHeader(308)
			}
		})

		err := resumableUpload(server.URL+"/upl", 3, UploadToCASOptions{
			SHA1: "abc",
			Data: bytes.NewReader([]byte(dataToUpload)),
			CommonOptions: CommonOptions{
				Client: client,
				Log:    logging.DefaultLogger,
			},
		})
		So(err, ShouldBeNil)
		So(uploaded.Bytes(), ShouldResemble, []byte(dataToUpload))
	})
}

////////////////////////////////////////////////////////////////////////////////

type mockedClocked struct {
	now time.Time
}

func (c *mockedClocked) Now() time.Time        { return c.now }
func (c *mockedClocked) Sleep(d time.Duration) { c.now = c.now.Add(d) }

func mockClock(now time.Time) {
	prev := clock
	clock = &mockedClocked{now: now}
	Reset(func() { clock = prev })
}

func mockServerWithMux(mux *http.ServeMux) (*httptest.Server, *http.Client) {
	server := httptest.NewServer(mux)
	transport := &http.Transport{
		Proxy: func(req *http.Request) (*url.URL, error) {
			return url.Parse(server.URL)
		},
	}
	Reset(func() { server.Close() })
	return server, &http.Client{Transport: transport}
}

func mockServerWithHandler(pattern string, handler http.HandlerFunc) (*httptest.Server, *http.Client) {
	mux := http.NewServeMux()
	mux.HandleFunc(pattern, handler)
	return mockServerWithMux(mux)
}

func mockRemoteService(handler http.HandlerFunc) *remoteService {
	server, client := mockServerWithHandler("/_ah/api/cas/v1/", handler)
	remote := &remoteService{
		client:     client,
		serviceURL: server.URL,
		log:        logging.DefaultLogger,
	}
	prev := newRemoteService
	newRemoteService = func(client *http.Client, url string, log logging.Logger) *remoteService {
		return remote
	}
	Reset(func() { newRemoteService = prev })
	return remote
}

func mockResumableUpload() {
	prev := resumableUpload
	resumableUpload = func(string, int64, UploadToCASOptions) error {
		return nil
	}
	Reset(func() { resumableUpload = prev })
}
