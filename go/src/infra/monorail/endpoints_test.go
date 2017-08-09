// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package monorail

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/retry/transient"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestEndpointsClient(t *testing.T) {
	t.Parallel()

	Convey("Endpoints client", t, func() {
		ctx := context.Background()

		Convey("Insert issue request succeeds", func(c C) {
			req := &InsertIssueRequest{
				ProjectId: "chromium",
				Issue: &Issue{
					Summary:     "Write tests for monorail client",
					Author:      &AtomPerson{"seanmccullough@chromium.org"},
					Owner:       &AtomPerson{"nodir@chromium.org"},
					Status:      StatusStarted,
					Cc:          []*AtomPerson{{"agable@chromium.org"}},
					Description: "We should keep our code coverage high, so write tests",
					Components:  []string{"Infra"},
					Labels:      []string{"M-53"},
				},
			}

			res := &InsertIssueResponse{
				Issue: &Issue{},
			}
			*res.Issue = *req.Issue
			res.Issue.Id = 1

			var insertIssueServer *httptest.Server
			insertIssueServer = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				c.So(r.URL.String(), ShouldEqual, "/projects/chromium/issues?sendEmail=false")

				actualReq := &Issue{}
				err := json.NewDecoder(r.Body).Decode(actualReq)
				c.So(err, ShouldBeNil)
				c.So(actualReq, ShouldResemble, req.Issue)

				err = json.NewEncoder(w).Encode(res.Issue)
				c.So(err, ShouldBeNil)
			}))
			defer insertIssueServer.Close()

			httpClient := &http.Client{Timeout: time.Second}
			client := NewEndpointsClient(httpClient, insertIssueServer.URL)
			actualRes, err := client.InsertIssue(ctx, req)
			So(err, ShouldBeNil)
			So(actualRes, ShouldResemble, res)
		})

		Convey("Insert issue with invalid request", func(c C) {
			req := &InsertIssueRequest{
				Issue: &Issue{
					Summary: "Write tests for monorail client",
					Author:  &AtomPerson{"seanmccullough@chromium.org"},
					Owner:   &AtomPerson{"nodir@chromium.org"},
					Status:  StatusStarted,
				},
			}

			httpClient := &http.Client{Timeout: time.Second}
			client := NewEndpointsClient(httpClient, "https://example.com")
			_, err := client.InsertIssue(ctx, req)
			So(err, ShouldErrLike, "no projectId")
		})

		Convey("Insert comment request", func(c C) {
			req := &InsertCommentRequest{
				Issue: &IssueRef{
					ProjectId: "chromium",
					IssueId:   1,
				},
				Comment: &InsertCommentRequest_Comment{
					Content: "Done",
					Updates: &Update{
						Status: StatusFixed,
					},
				},
			}

			Convey("Succeeds", func() {

				var serv *httptest.Server
				serv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					c.So(r.URL.String(), ShouldEqual, "/projects/chromium/issues/1/comments")

					actualReq := &InsertCommentRequest_Comment{}
					err := json.NewDecoder(r.Body).Decode(actualReq)
					c.So(err, ShouldBeNil)
					c.So(actualReq, ShouldResemble, req.Comment)

					fmt.Fprint(w, "{}")
				}))
				defer serv.Close()

				client := NewEndpointsClient(nil, serv.URL)
				_, err := client.InsertComment(ctx, req)
				So(err, ShouldBeNil)
			})

			Convey("Transient error", func(c C) {
				test := func(status int) {
					var serv *httptest.Server
					serv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
						w.WriteHeader(status)
					}))
					defer serv.Close()

					client := NewEndpointsClient(nil, serv.URL)
					_, err := client.InsertComment(ctx, req)
					So(err, ShouldNotBeNil)
					So(transient.Tag.In(err), ShouldBeTrue)
				}
				Convey("With HTTP 404", func() {
					test(404)
				})
				Convey("With HTTP 503", func() {
					test(503)
				})
			})
		})
	})
}
