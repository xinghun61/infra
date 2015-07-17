// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

	"github.com/luci/luci-go/common/clock/testclock"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry"
	. "github.com/smartystreets/goconvey/convey"
	"golang.org/x/net/context"
	cloudlog "google.golang.org/api/logging/v1beta3"
)

func TestCloudLoggingConfig(t *testing.T) {
	Convey(`A test logging config, using a test HTTP client/server`, t, func() {
		ctx := context.Background()

		config := &loggerConfig{
			projectName:  "test-project",
			resourceType: "test-resource",
			logsID:       "test-logs-id",
		}

		client := &http.Client{}

		Convey(`Requires a project name.`, func() {
			config.projectName = ""
			_, _, err := config.use(ctx, client)
			So(err, ShouldNotBeNil)
		})

		Convey(`Requires a resource type.`, func() {
			config.resourceType = ""
			_, _, err := config.use(ctx, client)
			So(err, ShouldNotBeNil)
		})

		Convey(`Requires a logs ID.`, func() {
			config.logsID = ""
			_, _, err := config.use(ctx, client)
			So(err, ShouldNotBeNil)
		})

		Convey(`Installs a bound cloud logger into a context.`, func() {
			ctx, closeFunc, err := config.use(ctx, client)
			So(err, ShouldBeNil)
			defer closeFunc()

			So(log.Get(ctx), ShouldHaveSameTypeAs, &boundCloudLogger{})
		})
	})
}

type cloudLogBundle struct {
	Entries []*cloudlog.LogEntry `json:"entries"`
}

type testCloudLoggingHandler struct {
	logC chan *cloudLogBundle
}

func (h *testCloudLoggingHandler) ServeHTTP(w http.ResponseWriter, req *http.Request) {
	defer req.Body.Close()

	if err := h.serveImpl(w, req); err != nil {
		err.writeError(w)
	}
}

func (h *testCloudLoggingHandler) serveImpl(w http.ResponseWriter, req *http.Request) *httpError {
	body, err := ioutil.ReadAll(req.Body)
	if err != nil {
		return internalServerError(err)
	}

	var l *cloudLogBundle
	if err := json.Unmarshal(body, &l); err != nil {
		return badRequest(err)
	}

	// Write an empty response to the client.
	w.Write([]byte("{}"))
	h.logC <- l
	return nil
}

func shouldMatchLog(actual interface{}, expected ...interface{}) string {
	l, ok := actual.(*cloudlog.LogEntry)
	if !ok {
		return "Actual: Not a cloud log entry."
	}

	if len(expected) != 1 {
		return "Expected: Must have exactly one expected value."
	}

	var e *cloudlog.LogEntry
	e, ok = expected[0].(*cloudlog.LogEntry)
	if !ok {
		return "Expected: Not a single cloud log entry."
	}

	lc := *l
	ec := *e

	if err := ShouldResemble(lc.Metadata, ec.Metadata); err != "" {
		return err
	}
	return ShouldResemble(lc, ec)
}

func TestCloudLogging(t *testing.T) {
	Convey(`A cloud logging instance using a test HTTP client/server`, t, func() {
		ctx, _ := testclock.UseTime(context.Background(), time.Date(2015, 1, 1, 0, 0, 0, 0, time.UTC))

		// Do not retry.
		ctx = retry.Use(ctx, func(context.Context) retry.Iterator {
			return &retry.Limited{}
		})

		h := &testCloudLoggingHandler{
			logC: make(chan *cloudLogBundle, 1),
		}
		srv := httptest.NewServer(h)
		defer srv.Close()

		tr := &http.Transport{
			DialTLS: func(network, addr string) (net.Conn, error) {
				u, err := url.Parse(srv.URL)
				if err != nil {
					return nil, err
				}
				return net.Dial(network, u.Host)
			},
		}
		client := &http.Client{
			Transport: tr,
		}

		config := loggerConfig{
			projectName:  "test-project",
			resourceType: "test-resource",
			logsID:       "test-logs-id",
		}

		service, err := cloudlog.New(client)
		So(err, ShouldBeNil)

		cl := newCloudLogging(ctx, &config, service)
		defer cl.finish()

		Convey(`A bound cloud logging instance`, func() {
			l := cl.bind(ctx)

			Convey(`Can publish logging data.`, func() {
				l.Infof("Message at %s", "INFO")

				bundle := <-h.logC
				So(len(bundle.Entries), ShouldEqual, 1)
				So(bundle.Entries[0], shouldMatchLog, &cloudlog.LogEntry{
					InsertId: "-0-0",
					Metadata: &cloudlog.LogEntryMetadata{
						ProjectId: "test-project",
						Severity:  "INFO",
						Timestamp: "2015-01-01T00:00:00Z",
					},
					TextPayload: "Message at INFO",
				})
			})

			Convey(`Will batch logging data.`, func() {
				cl.testLogAckC = make(chan []*logEntry, 1)

				// The first message will be read immediately.
				l.Infof("Initial unbatched message.")
				<-cl.testLogAckC

				// The next set of messages will be batched, since we're not release our
				// HTTP server yet.
				for i := 0; i < cloudLoggingBatchSize; i++ {
					l.Infof("Batch message #%d", i)
				}
				<-cl.testLogAckC

				// Read the first bundle.
				bundle := <-h.logC
				So(len(bundle.Entries), ShouldEqual, 1)
				So(bundle.Entries[0], shouldMatchLog, &cloudlog.LogEntry{
					InsertId: "-0-0",
					Metadata: &cloudlog.LogEntryMetadata{
						ProjectId: "test-project",
						Severity:  "INFO",
						Timestamp: "2015-01-01T00:00:00Z",
					},
					TextPayload: "Initial unbatched message.",
				})

				// Read the second bundle.
				bundle = <-h.logC
				So(len(bundle.Entries), ShouldEqual, cloudLoggingBatchSize)
				for i, entry := range bundle.Entries {
					So(entry, shouldMatchLog, &cloudlog.LogEntry{
						InsertId: fmt.Sprintf("-1-%d", i),
						Metadata: &cloudlog.LogEntryMetadata{
							ProjectId: "test-project",
							Severity:  "INFO",
							Timestamp: "2015-01-01T00:00:00Z",
						},
						TextPayload: fmt.Sprintf("Batch message #%d", i),
					})
				}
			})
		})
	})
}
