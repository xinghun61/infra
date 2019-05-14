// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Package util implements helper functions that are used in other packages.
package util

import (
	"context"
	"encoding/base64"
	"fmt"
	"io/ioutil"
	"net/http"
	"strings"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/gae/service/urlfetch"
)

var (
	// SampleValidAssignerCfg is a sample assigner config to be used in
	// unit tests.
	SampleValidAssignerCfg = `
		id: "test-assigner"
		owners: "foo@google.com"
		interval: <
			seconds: 60
		>
		issue_query: <
			q: "-has:owner Ops-Alerts=test"
			project_names: "chromium"
		>
		assignees: <
			email: "oncall1@test.com"
		>
		ccs: <
			email: "secondary1@test.com"
		>
		ccs: <
			email: "secondary2@test.com"
		>
	`
)

// EqualSortedLists returns true if lists contain the same sequence of
// strings.
func EqualSortedLists(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i, s := range a {
		if s != b[i] {
			return false
		}
	}
	return true
}

// SetupTaskIndexes adds indexes for Task entities to be used by unit tests.
func SetupTaskIndexes(c context.Context) {
	datastore.GetTestable(c).AddIndexes(&datastore.IndexDefinition{
		Kind:     "Task",
		Ancestor: true,
		SortBy: []datastore.IndexColumn{
			{Property: "WasNoopSuccess"},
			{Property: "ExpectedStart", Descending: true},
		},
	})

	datastore.GetTestable(c).AddIndexes(&datastore.IndexDefinition{
		Kind:     "Task",
		Ancestor: true,
		SortBy: []datastore.IndexColumn{
			{Property: "ExpectedStart", Descending: true},
		},
	})
}

// CreateTestContext creates a test context to be used in unit tests.
func CreateTestContext() context.Context {
	c := memory.Use(context.Background())
	SetupTaskIndexes(c)

	tq := taskqueue.GetTestable(c)
	tq.CreateQueue("schedule-assigners")
	tq.CreateQueue("run-assigners")

	c = urlfetch.Set(c, &MockHTTPTransport{
		Responses: map[string]string{},
	})
	return c
}

// MockHTTPTransport is a test support type to mock out request/response pairs.
type MockHTTPTransport struct {
	Responses map[string]string
}

// RoundTrip implements http.RoundTripper
func (t MockHTTPTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	response := &http.Response{
		Header:     make(http.Header),
		Request:    req,
		StatusCode: http.StatusOK,
	}
	responseBody, ok := t.Responses[req.URL.String()]
	if !ok {
		response.StatusCode = http.StatusNotFound
		response.Body = ioutil.NopCloser(strings.NewReader(
			fmt.Sprintf("Page not found: %s", req.URL.String()),
		))
		return response, nil
	}

	if strings.ToLower(req.FormValue("format")) == "text" {
		responseBody = base64.StdEncoding.EncodeToString([]byte(responseBody))
	}

	response.Body = ioutil.NopCloser(strings.NewReader(responseBody))
	return response, nil
}
