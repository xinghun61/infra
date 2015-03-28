// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"net/url"
	"reflect"
	"strings"
	"testing"
	"time"

	"infra/libs/logging"

	. "github.com/smartystreets/goconvey/convey"
)

func TestRemoteService(t *testing.T) {
	mockInitiateUpload := func(c C, response string) (*uploadSession, error) {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			c.So(r.URL.Path, ShouldEqual, "/_ah/api/cas/v1/upload/SHA1/abc")
			c.So(r.Method, ShouldEqual, "POST")
			w.Write([]byte(response))
		})
		return remote.initiateUpload("abc")
	}

	mockFinalizeUpload := func(c C, response string) (bool, error) {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			c.So(r.URL.Path, ShouldEqual, "/_ah/api/cas/v1/finalize/abc")
			c.So(r.Method, ShouldEqual, "POST")
			w.Write([]byte(response))
		})
		return remote.finalizeUpload("abc")
	}

	mockRegisterInstance := func(c C, response string) (*registerInstanceResponse, error) {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			c.So(r.URL.Path, ShouldEqual, "/_ah/api/repo/v1/instance")
			c.So(r.URL.Query().Get("package_name"), ShouldEqual, "pkgname")
			c.So(r.URL.Query().Get("instance_id"), ShouldEqual, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
			c.So(r.Method, ShouldEqual, "POST")
			w.Write([]byte(response))
		})
		return remote.registerInstance("pkgname", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	}

	mockFetchInstance := func(c C, response string) (*fetchInstanceResponse, error) {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			c.So(r.URL.Path, ShouldEqual, "/_ah/api/repo/v1/instance")
			c.So(r.URL.Query().Get("package_name"), ShouldEqual, "pkgname")
			c.So(r.URL.Query().Get("instance_id"), ShouldEqual, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
			c.So(r.Method, ShouldEqual, "GET")
			w.Write([]byte(response))
		})
		return remote.fetchInstance("pkgname", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	}

	mockFetchACL := func(c C, response string) ([]PackageACL, error) {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			c.So(r.URL.Path, ShouldEqual, "/_ah/api/repo/v1/acl")
			c.So(r.URL.Query().Get("package_path"), ShouldEqual, "pkgname")
			c.So(r.Method, ShouldEqual, "GET")
			w.Write([]byte(response))
		})
		return remote.fetchACL("pkgname")
	}

	mockModifyACL := func(c C, changes []PackageACLChange, request, response string) error {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			c.So(r.URL.Path, ShouldEqual, "/_ah/api/repo/v1/acl")
			c.So(r.URL.Query().Get("package_path"), ShouldEqual, "pkgname")
			c.So(r.Method, ShouldEqual, "POST")
			body, err := ioutil.ReadAll(r.Body)
			c.So(err, ShouldBeNil)
			c.So(string(body), ShouldEqual, request)
			w.Write([]byte(response))
		})
		return remote.modifyACL("pkgname", changes)
	}

	Convey("makeRequest POST works", t, func(c C) {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			c.So(r.Method, ShouldEqual, "POST")
			c.So(r.URL.Path, ShouldEqual, "/_ah/api/cas/v1/method")
			w.Write([]byte(`{"value":"123"}`))
		})
		var reply struct {
			Value string `json:"value"`
		}
		err := remote.makeRequest("cas/v1/method", "POST", nil, &reply)
		So(err, ShouldBeNil)
		So(reply.Value, ShouldEqual, "123")
	})

	Convey("makeRequest GET works", t, func(c C) {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			c.So(r.Method, ShouldEqual, "GET")
			c.So(r.URL.Path, ShouldEqual, "/_ah/api/cas/v1/method")
			w.Write([]byte(`{"value":"123"}`))
		})
		var reply struct {
			Value string `json:"value"`
		}
		err := remote.makeRequest("cas/v1/method", "GET", nil, &reply)
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
		err := remote.makeRequest("cas/v1/method", "POST", nil, &reply)
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
		err := remote.makeRequest("cas/v1/method", "POST", nil, &reply)
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
		err := remote.makeRequest("cas/v1/method", "POST", nil, &reply)
		So(err, ShouldNotBeNil)
		So(calls, ShouldEqual, 10)
	})

	Convey("initiateUpload ALREADY_UPLOADED", t, func(c C) {
		s, err := mockInitiateUpload(c, `{"status":"ALREADY_UPLOADED"}`)
		So(err, ShouldBeNil)
		So(s, ShouldBeNil)
	})

	Convey("initiateUpload SUCCESS", t, func(c C) {
		s, err := mockInitiateUpload(c, `{"status":"SUCCESS","upload_session_id":"123","upload_url":"http://localhost"}`)
		So(err, ShouldBeNil)
		So(s, ShouldResemble, &uploadSession{
			ID:  "123",
			URL: "http://localhost",
		})
	})

	Convey("initiateUpload ERROR", t, func(c C) {
		s, err := mockInitiateUpload(c, `{"status":"ERROR","error_message":"boo"}`)
		So(err, ShouldNotBeNil)
		So(s, ShouldBeNil)
	})

	Convey("initiateUpload unknown status", t, func(c C) {
		s, err := mockInitiateUpload(c, `{"status":"???"}`)
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

	Convey("finalizeUpload MISSING", t, func(c C) {
		finished, err := mockFinalizeUpload(c, `{"status":"MISSING"}`)
		So(err, ShouldNotBeNil)
		So(finished, ShouldBeFalse)
	})

	Convey("finalizeUpload UPLOADING", t, func(c C) {
		finished, err := mockFinalizeUpload(c, `{"status":"UPLOADING"}`)
		So(err, ShouldBeNil)
		So(finished, ShouldBeFalse)
	})

	Convey("finalizeUpload VERIFYING", t, func(c C) {
		finished, err := mockFinalizeUpload(c, `{"status":"VERIFYING"}`)
		So(err, ShouldBeNil)
		So(finished, ShouldBeFalse)
	})

	Convey("finalizeUpload PUBLISHED", t, func(c C) {
		finished, err := mockFinalizeUpload(c, `{"status":"PUBLISHED"}`)
		So(err, ShouldBeNil)
		So(finished, ShouldBeTrue)
	})

	Convey("finalizeUpload ERROR", t, func(c C) {
		finished, err := mockFinalizeUpload(c, `{"status":"ERROR","error_message":"boo"}`)
		So(err, ShouldNotBeNil)
		So(finished, ShouldBeFalse)
	})

	Convey("finalizeUpload unknown status", t, func(c C) {
		finished, err := mockFinalizeUpload(c, `{"status":"???"}`)
		So(err, ShouldNotBeNil)
		So(finished, ShouldBeFalse)
	})

	Convey("finalizeUpload bad reply", t, func(c C) {
		remote := mockRemoteService(func(w http.ResponseWriter, r *http.Request) {
			c.So(r.URL.Path, ShouldEqual, "/_ah/api/cas/v1/finalize/abc")
			w.WriteHeader(403)
		})
		finished, err := remote.finalizeUpload("abc")
		So(err, ShouldNotBeNil)
		So(finished, ShouldBeFalse)
	})

	Convey("registerInstance REGISTERED", t, func(c C) {
		result, err := mockRegisterInstance(c, `{
			"status": "REGISTERED",
			"instance": {
				"registered_by": "user:abc@example.com",
				"registered_ts": "1420244414571500"
			}
		}`)
		So(err, ShouldBeNil)
		So(result, ShouldResemble, &registerInstanceResponse{
			Info: packageInstanceInfo{
				RegisteredBy: "user:abc@example.com",
				RegisteredTs: time.Unix(0, 1420244414571500000),
			},
		})
	})

	Convey("registerInstance ALREADY_REGISTERED", t, func(c C) {
		result, err := mockRegisterInstance(c, `{
			"status": "ALREADY_REGISTERED",
			"instance": {
				"registered_by": "user:abc@example.com",
				"registered_ts": "1420244414571500"
			}
		}`)
		So(err, ShouldBeNil)
		So(result, ShouldResemble, &registerInstanceResponse{
			AlreadyRegistered: true,
			Info: packageInstanceInfo{
				RegisteredBy: "user:abc@example.com",
				RegisteredTs: time.Unix(0, 1420244414571500000),
			},
		})
	})

	Convey("registerInstance UPLOAD_FIRST", t, func(c C) {
		result, err := mockRegisterInstance(c, `{
			"status": "UPLOAD_FIRST",
			"upload_session_id": "upload_session_id",
			"upload_url": "http://upload_url"
		}`)
		So(err, ShouldBeNil)
		So(result, ShouldResemble, &registerInstanceResponse{
			UploadSession: &uploadSession{
				ID:  "upload_session_id",
				URL: "http://upload_url",
			},
		})
	})

	Convey("registerInstance ERROR", t, func(c C) {
		result, err := mockRegisterInstance(c, `{
			"status": "ERROR",
			"error_message": "Some error message"
		}`)
		So(err, ShouldNotBeNil)
		So(result, ShouldBeNil)
	})

	Convey("registerInstance unknown status", t, func(c C) {
		result, err := mockRegisterInstance(c, `{"status":"???"}`)
		So(err, ShouldNotBeNil)
		So(result, ShouldBeNil)
	})

	Convey("fetchInstance SUCCESS", t, func(c C) {
		result, err := mockFetchInstance(c, `{
			"status": "SUCCESS",
			"instance": {
				"registered_by": "user:abc@example.com",
				"registered_ts": "1420244414571500"
			},
			"fetch_url": "https://fetch_url"
		}`)
		So(err, ShouldBeNil)
		So(result, ShouldResemble, &fetchInstanceResponse{
			Info: packageInstanceInfo{
				RegisteredBy: "user:abc@example.com",
				RegisteredTs: time.Unix(0, 1420244414571500000),
			},
			FetchURL: "https://fetch_url",
		})
	})

	Convey("fetchInstance PACKAGE_NOT_FOUND", t, func(c C) {
		result, err := mockFetchInstance(c, `{"status": "PACKAGE_NOT_FOUND"}`)
		So(err, ShouldNotBeNil)
		So(result, ShouldBeNil)
	})

	Convey("fetchInstance INSTANCE_NOT_FOUND", t, func(c C) {
		result, err := mockFetchInstance(c, `{"status": "INSTANCE_NOT_FOUND"}`)
		So(err, ShouldNotBeNil)
		So(result, ShouldBeNil)
	})

	Convey("fetchInstance ERROR", t, func(c C) {
		result, err := mockFetchInstance(c, `{
			"status": "ERROR",
			"error_message": "Some error message"
		}`)
		So(err, ShouldNotBeNil)
		So(result, ShouldBeNil)
	})

	Convey("fetchACL SUCCESS", t, func(c C) {
		result, err := mockFetchACL(c, `{
			"status": "SUCCESS",
			"acls": {
				"acls": [
					{
						"package_path": "a",
						"role": "OWNER",
						"principals": ["user:a", "group:b"],
						"modified_by": "user:abc@example.com",
						"modified_ts": "1420244414571500"
					},
					{
						"package_path": "a/b",
						"role": "READER",
						"principals": ["group:c"],
						"modified_by": "user:abc@example.com",
						"modified_ts": "1420244414571500"
					}
				]
			}
		}`)
		So(err, ShouldBeNil)
		So(result, ShouldResemble, []PackageACL{
			{
				PackagePath: "a",
				Role:        "OWNER",
				Principals:  []string{"user:a", "group:b"},
				ModifiedBy:  "user:abc@example.com",
				ModifiedTs:  time.Unix(0, 1420244414571500000),
			},
			{
				PackagePath: "a/b",
				Role:        "READER",
				Principals:  []string{"group:c"},
				ModifiedBy:  "user:abc@example.com",
				ModifiedTs:  time.Unix(0, 1420244414571500000),
			},
		})
	})

	Convey("fetchACL ERROR", t, func(c C) {
		result, err := mockFetchACL(c, `{
			"status": "ERROR",
			"error_message": "Some error message"
		}`)
		So(err, ShouldNotBeNil)
		So(result, ShouldBeNil)
	})

	Convey("modifyACL SUCCESS", t, func(c C) {
		expected := `{
			"changes": [
				{
					"action": "GRANT",
					"role": "OWNER",
					"principal": "user:a@example.com"
				},
				{
					"action": "REVOKE",
					"role": "READER",
					"principal": "user:b@example.com"
				}
			]
		}`
		// Strip " ", "\t" and "\n".
		expected = strings.Replace(expected, " ", "", -1)
		expected = strings.Replace(expected, "\n", "", -1)
		expected = strings.Replace(expected, "\t", "", -1)

		err := mockModifyACL(c, []PackageACLChange{
			{
				Action:    GrantRole,
				Role:      "OWNER",
				Principal: "user:a@example.com",
			},
			{
				Action:    RevokeRole,
				Role:      "READER",
				Principal: "user:b@example.com",
			},
		}, expected, `{"status":"SUCCESS"}`)
		So(err, ShouldBeNil)
	})

	Convey("modifyACL ERROR", t, func(c C) {
		err := mockModifyACL(c, []PackageACLChange{}, `{"changes":null}`, `{
			"status": "ERROR",
			"error_message": "Error message"
		}`)
		So(err, ShouldNotBeNil)
	})
}

////////////////////////////////////////////////////////////////////////////////

type expectedHTTPCall struct {
	Method string
	Path   string
	Reply  string
	Query  url.Values
	Status int
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
		exp := expectedHTTPCall{}
		if index >= len(expectations) {
			msg = "Unexpected call"
		} else {
			// Fill in defaults.
			exp = expectations[index]
			if exp.Method == "" {
				exp.Method = "GET"
			}
			if exp.Query == nil {
				exp.Query = url.Values{}
			}
			// Check that request is what it is expected to be.
			if r.URL.Path != exp.Path {
				msg = fmt.Sprintf("Expecting call to %s, got %s instead", exp.Path, r.URL.Path)
			} else if !reflect.DeepEqual(r.URL.Query(), exp.Query) {
				msg = fmt.Sprintf("Expecting query string %v, got %v instead", exp.Query, r.URL.Query())
			} else if r.Method != exp.Method {
				msg = fmt.Sprintf("Expecting %s to %s, got %s instead", exp.Method, exp.Path, r.Method)
			}
		}

		// Error?
		if msg != "" {
			w.WriteHeader(400)
			w.Write([]byte(msg))
			return
		}

		// Mocked reply.
		if exp.Status != 0 {
			w.WriteHeader(exp.Status)
		}
		if exp.Reply != "" {
			w.Write([]byte(exp.Reply))
		}
		index++
	})
}
