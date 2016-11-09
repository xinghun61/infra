// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"net/http"
	"testing"
	"time"

	"golang.org/x/net/context"

	logging "google.golang.org/api/logging/v2"

	. "github.com/smartystreets/goconvey/convey"
)

func TestClient(t *testing.T) {
	Convey("PushEntries works", t, func() {
		ctx := testContext()

		opts := ClientOptions{
			ClientID: ClientID{
				ResourceType: "res-type",
				ResourceID:   "res-id",
				LogID:        "log-id",
			},
			Client:    http.DefaultClient,
			ProjectID: "proj-id",
		}

		requests := []*logging.WriteLogEntriesRequest{}
		writeFunc := func(ctx context.Context, req *logging.WriteLogEntriesRequest) error {
			requests = append(requests, req)
			return nil
		}

		ts, err := time.Parse(time.RFC3339, "2015-10-02T15:00:00Z")
		So(err, ShouldBeNil)

		c, err := clientWithMockWrite(opts, writeFunc)
		So(err, ShouldBeNil)
		err = c.PushEntries(ctx, []*Entry{
			{
				InsertID:    "insert-id",
				Timestamp:   ts,
				Severity:    Debug,
				TextPayload: "hi",
			},
		})
		So(err, ShouldBeNil)
		So(len(requests), ShouldEqual, 1)
		So(requests[0].LogName, ShouldEqual, "projects/proj-id/logs/log-id")
		So(requests[0].Labels, ShouldResemble, map[string]string{
			"cloudtail/resource_id":   "res-id",
			"cloudtail/resource_type": "res-type",
		})
		So(requests[0].Resource, ShouldResemble, &logging.MonitoredResource{
			Type: "global",
			Labels: map[string]string{
				"project_id": "proj-id",
			},
		})
		So(len(requests[0].Entries), ShouldEqual, 1)
		So(requests[0].Entries[0], ShouldResemble, &logging.LogEntry{
			InsertId:    "insert-id",
			Severity:    "DEBUG",
			TextPayload: "hi",
			Timestamp:   "2015-10-02T15:00:00Z",
		})
	})
}

func clientWithMockWrite(opts ClientOptions, writeFunc writeFunc) (Client, error) {
	c, err := NewClient(opts)
	if err == nil {
		cl := c.(*loggingClient)
		cl.writeFunc = writeFunc
	}
	return c, err
}
