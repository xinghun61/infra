// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"crypto/tls"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/clock/testclock"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/retry"
	. "github.com/smartystreets/goconvey/convey"
	"golang.org/x/net/context"
)

func init() {
	backoffTestMode = true
}

// testEndpointServiceHandler is a testing HTTP server. It is not goroutine-safe.
type testEndpointServiceHandler struct {
	messages    [][]byte
	failures    int
	connections int
	errors      int
}

func (h *testEndpointServiceHandler) ServeHTTP(w http.ResponseWriter, req *http.Request) {
	defer req.Body.Close()
	h.connections++

	var err *httpError
	if h.failures > 0 {
		err = internalServerError(fmt.Errorf("Intentional failure #%d", h.failures))
		h.failures--
	} else if req.Method == "POST" {
		err = h.handlePOST(w, req)
	} else {
		err = &httpError{fmt.Errorf("Unsupport method %q.", req.Method), http.StatusNotFound}
	}
	if err != nil {
		err.writeError(w)
		if !err.ok() {
			h.errors++
		}
	}
}

func (h *testEndpointServiceHandler) handlePOST(w http.ResponseWriter, req *http.Request) *httpError {
	if req.Header.Get("content-type") != protobufContentType {
		return badRequest(fmt.Errorf("Unknown content type: %q", req.Header.Get("content-type")))
	}
	if req.Header.Get("user-agent") != monitoringEndpointUserAgent {
		return badRequest(fmt.Errorf("Unknown user agent: %q", req.Header.Get("user-agent")))
	}

	data, err := ioutil.ReadAll(req.Body)
	if err != nil {
		return internalServerError(err)
	}

	h.messages = append(h.messages, data)
	// The actual monitoring endpoint always responds 204.
	return noContent(nil)
}

// TestEndpoint tests the endpoint implementation and API.
func TestEndpointService(t *testing.T) {
	t.Parallel()

	Convey(`An endpoint service connected to a testing HTTP server`, t, func() {
		ctx, tc := testclock.UseTime(context.Background(), time.Date(2015, 1, 1, 0, 0, 0, 0, time.UTC))

		// Retry up to ten times without delaying.
		ctx = context.WithValue(ctx, backoffPolicyKey, func() retry.Iterator {
			return &retry.Limited{Retries: 10}
		})

		h := &testEndpointServiceHandler{}
		srv := httptest.NewTLSServer(h)
		defer srv.Close()

		tr := &http.Transport{
			TLSClientConfig: &tls.Config{
				InsecureSkipVerify: true,
			},
		}
		client := &http.Client{
			Transport: tr,
		}

		c := &endpointServiceImpl{
			endpointConfig: endpointConfig{url: srv.URL},
			client:         client,
		}

		msg := bytes.Repeat([]byte{0x60, 0x0d, 0xd0, 0x65}, 32)
		Convey(`Successfully posts a message.`, func() {
			So(c.send(ctx, msg), ShouldBeNil)

			So(h.connections, ShouldEqual, 1)
			So(h.errors, ShouldEqual, 0)
			So(h.messages, ShouldResemble, [][]byte{msg})
		})

		Convey(`Retries sending when an error is encountered.`, func() {
			tc.SetTimerCallback(func(t clock.Timer) {
				tc.Add(time.Second)
			})
			h.failures = 4
			So(c.send(ctx, msg), ShouldBeNil)

			So(h.connections, ShouldEqual, 5)
			So(h.errors, ShouldEqual, 4)
			So(h.messages, ShouldResemble, [][]byte{msg})
		})

		Convey(`Returns a transient error when a send completely fails.`, func() {
			h.failures = 11
			err := c.send(ctx, msg)
			So(err, ShouldNotBeNil)
			So(errors.IsTransient(err), ShouldBeTrue)

			So(h.connections, ShouldEqual, 11)
			So(h.errors, ShouldEqual, 11)
			So(h.messages, ShouldResemble, [][]byte(nil))
		})
	})
}
