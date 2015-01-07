// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"encoding/json"
	"fmt"
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

	mockRegisterPackage := func(response string) (*registerPackageResponse, error) {
		request := registerPackageRequest{
			PackageName: "pkgname",
			InstanceID:  "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		}
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			So(r.URL.Path, ShouldEqual, "/_ah/api/repo/v1/register_package")
			var decoded registerPackageRequest
			err := json.NewDecoder(r.Body).Decode(&decoded)
			So(err, ShouldBeNil)
			So(decoded, ShouldResemble, request)
			w.Write([]byte(response))
		})
		return remote.registerPackage(&request)
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
		err := remote.makeRequest("cas/v1/method", nil, &reply)
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
		err := remote.makeRequest("cas/v1/method", nil, &reply)
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
		err := remote.makeRequest("cas/v1/method", nil, &reply)
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
		err := remote.makeRequest("cas/v1/method", nil, &reply)
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

	Convey("registerPackage REGISTERED", t, func() {
		result, err := mockRegisterPackage(`{
      "status": "REGISTERED",
      "registered_by": "user:abc@example.com",
      "registered_ts": "1420244414571500"
    }`)
		So(err, ShouldBeNil)
		So(result, ShouldResemble, &registerPackageResponse{
			RegisteredBy: "user:abc@example.com",
			RegisteredTs: time.Unix(0, 1420244414571500000),
		})
	})

	Convey("registerPackage ALREADY_REGISTERED", t, func() {
		result, err := mockRegisterPackage(`{
      "status": "ALREADY_REGISTERED",
      "registered_by": "user:abc@example.com",
      "registered_ts": "1420244414571500"
    }`)
		So(err, ShouldBeNil)
		So(result, ShouldResemble, &registerPackageResponse{
			AlreadyRegistered: true,
			RegisteredBy:      "user:abc@example.com",
			RegisteredTs:      time.Unix(0, 1420244414571500000),
		})
	})

	Convey("registerPackage UPLOAD_FIRST", t, func() {
		result, err := mockRegisterPackage(`{
      "status": "UPLOAD_FIRST",
      "upload_session_id": "upload_session_id",
      "upload_url": "http://upload_url"
    }`)
		So(err, ShouldBeNil)
		So(result, ShouldResemble, &registerPackageResponse{
			UploadSession: &uploadSession{
				ID:  "upload_session_id",
				URL: "http://upload_url",
			},
		})
	})

	Convey("registerPackage ERROR", t, func() {
		result, err := mockRegisterPackage(`{
      "status": "ERROR",
      "error_message": "Some error message"
    }`)
		So(err, ShouldNotBeNil)
		So(result, ShouldBeNil)
	})

	Convey("registerPackage unknown status", t, func() {
		result, err := mockRegisterPackage(`{"status":"???"}`)
		So(err, ShouldNotBeNil)
		So(result, ShouldBeNil)
	})
}

////////////////////////////////////////////////////////////////////////////////

type expectedHTTPCall struct {
	URL   string
	Reply string
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
	server, client := mockServerWithHandler("/", handler)
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

func mockRemoteServiceWithExpectations(expectations []expectedHTTPCall) *remoteService {
	index := 0
	return mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
		// Can't use So(...) assertions here. They are not recognized. Return
		// errors via HTTP instead, to let the main test case catch them.
		msg := ""
		if index >= len(expectations) {
			msg = "Unexpected call"
		} else if r.URL.Path != expectations[index].URL {
			msg = fmt.Sprintf("Expecting call to %s, got %s instead", expectations[index].URL, r.URL.Path)
		}
		if msg != "" {
			w.WriteHeader(400)
			w.Write([]byte(msg))
		} else {
			if expectations[index].Reply != "" {
				w.Write([]byte(expectations[index].Reply))
			}
			index++
		}
	})
}
