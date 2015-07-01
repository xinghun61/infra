// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"net/http"
	"testing"
	"time"

	logging "google.golang.org/api/logging/v1beta3"

	. "github.com/smartystreets/goconvey/convey"
)

func TestClient(t *testing.T) {
	Convey("PushEntries works", t, func() {
		opts := ClientOptions{
			Client:       http.DefaultClient,
			ProjectID:    "proj-id",
			ResourceType: "res-type",
			ResourceID:   "res-id",
			LogID:        "log-id",
		}

		requests := []*logging.WriteLogEntriesRequest{}
		writeFunc := func(projID, logID string, req *logging.WriteLogEntriesRequest) error {
			So(projID, ShouldEqual, "proj-id")
			So(logID, ShouldEqual, "log-id")
			requests = append(requests, req)
			return nil
		}

		ts, err := time.Parse(time.RFC3339, "2015-10-02T15:00:00Z")
		So(err, ShouldBeNil)

		c, err := clientWithMockWrite(opts, writeFunc)
		So(err, ShouldBeNil)
		err = c.PushEntries([]Entry{
			{
				Timestamp:   ts,
				Severity:    Debug,
				TextPayload: "hi",
			},
		})
		So(err, ShouldBeNil)
		So(len(requests), ShouldEqual, 1)
		So(requests[0].CommonLabels, ShouldResemble, map[string]string{
			"compute.googleapis.com/resource_id":   "res-id",
			"compute.googleapis.com/resource_type": "res-type",
		})
		So(len(requests[0].Entries), ShouldEqual, 1)
		So(requests[0].Entries[0].TextPayload, ShouldEqual, "hi")
		So(requests[0].Entries[0].Metadata, ShouldResemble, &logging.LogEntryMetadata{
			Severity:    "DEBUG",
			ServiceName: "compute.googleapis.com",
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
