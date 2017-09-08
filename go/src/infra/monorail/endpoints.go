// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package monorail

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"net/url"
	"strings"

	"golang.org/x/net/context"
	"golang.org/x/net/context/ctxhttp"
	"google.golang.org/grpc"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry/transient"
)

// epClient implements MonorailClient by sending requests to Monorail's
// Cloud Endpoints API.
// See https://monorail-staging.appspot.com/_ah/api/explorer#p/monorail/v1/
type epClient struct {
	HTTP *http.Client
	// url is root of API without trailing slash,
	// e.g. "https://monorail-staging.appspot.com/_ah/api/monorail/v1"
	url string
}

// NewEndpointsClient creates a MonorailClient that send requests to
// Monorail Cloud Endpoints API at url.
//
// Example of url: "https://monorail-staging.appspot.com/_ah/api/monorail/v1"
//
// Methods do not implement retries.
// Use "go.chromium.org/luci/common/errors".IsTransient to check
// if an error is transient.
//
// Client methods return an error on any grpc.CallOption.
func NewEndpointsClient(client *http.Client, url string) MonorailClient {
	return &epClient{HTTP: client, url: strings.TrimSuffix(url, "/")}
}

func (c *epClient) call(ctx context.Context, method, urlSuffix string, request, response interface{}) error {
	client := c.HTTP
	if client == nil {
		client = http.DefaultClient
	}

	// Limit ctx deadline to timeout set in client.
	if client.Timeout > 0 {
		clientDeadline := clock.Now(ctx).Add(client.Timeout)
		if deadline, ok := ctx.Deadline(); !ok || deadline.After(clientDeadline) {
			ctx, _ = context.WithDeadline(ctx, clientDeadline)
		}
	}

	// Convert request object to JSON.
	reqBuf := &bytes.Buffer{}
	if request != nil {
		if err := json.NewEncoder(reqBuf).Encode(request); err != nil {
			return err
		}
	}

	// Make an HTTP request.
	req, err := http.NewRequest(method, c.url+urlSuffix, reqBuf)
	if err != nil {
		return fmt.Errorf("could not make a request to %s: %s", req.URL, err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	// Send the request.
	logging.Debugf(ctx, "%s %s %s", method, req.URL, reqBuf.Bytes())
	res, err := ctxhttp.Do(ctx, client, req)
	if err != nil {
		return transient.Tag.Apply(err)
	}
	defer res.Body.Close()

	// Check HTTP status code.
	if res.StatusCode != http.StatusOK {
		text, _ := ioutil.ReadAll(io.LimitReader(res.Body, 1024))
		err := fmt.Errorf("unexpected status %q. Response: %s", res.Status, text)
		if res.StatusCode == http.StatusNotFound || res.StatusCode > 500 {
			// Cloud Endpoints often flake with HTTP 404.
			// Treat such responses transient errors.
			err = transient.Tag.Apply(err)
		}
		return err
	}

	if response == nil {
		return nil
	}
	return json.NewDecoder(res.Body).Decode(response)
}

func (c *epClient) InsertIssue(ctx context.Context, req *InsertIssueRequest, options ...grpc.CallOption) (*InsertIssueResponse, error) {
	if err := checkOptions(options); err != nil {
		return nil, err
	}
	if err := req.Validate(); err != nil {
		return nil, err
	}
	url := fmt.Sprintf("/projects/%s/issues?sendEmail=%v", req.ProjectId, req.SendEmail)
	res := &InsertIssueResponse{&Issue{}}
	return res, c.call(ctx, "POST", url, &req.Issue, res.Issue)
}

func (c *epClient) InsertComment(ctx context.Context, req *InsertCommentRequest, options ...grpc.CallOption) (*InsertCommentResponse, error) {
	if err := checkOptions(options); err != nil {
		return nil, err
	}
	params := url.Values{}
	if req.SendEmail {
		params.Set("sendEmail", "true")
	}
	u := fmt.Sprintf("/projects/%s/issues/%d/comments?%s", req.Issue.ProjectId, req.Issue.IssueId, params.Encode())
	return &InsertCommentResponse{}, c.call(ctx, "POST", u, req.Comment, nil)
}

func (c *epClient) IssuesList(ctx context.Context, req *IssuesListRequest, options ...grpc.CallOption) (*IssuesListResponse, error) {
	if err := checkOptions(options); err != nil {
		return nil, err
	}

	args := url.Values{}
	args.Set("can", strings.ToLower(req.Can.String()))
	args.Set("q", req.Q)
	args.Set("label", req.Label)
	args.Set("maxResults", fmt.Sprintf("%d", req.MaxResults))
	args.Set("owner", req.Owner)
	args.Set("publishedMax", fmt.Sprintf("%d", req.PublishedMax))
	args.Set("publishedMin", fmt.Sprintf("%d", req.PublishedMin))
	args.Set("sort", req.Sort)
	args.Set("startIndex", fmt.Sprintf("%d", req.StartIndex))
	args.Set("status", req.Status)
	args.Set("updatedMax", fmt.Sprintf("%d", req.UpdatedMax))
	args.Set("updatedMin", fmt.Sprintf("%d", req.UpdatedMin))

	url := fmt.Sprintf("/projects/%s/issues?%s", req.ProjectId, args.Encode())
	res := &IssuesListResponse{}
	err := c.call(ctx, "GET", url, nil, res)
	if err != nil {
		return nil, err
	}
	return res, nil
}

func checkOptions(options []grpc.CallOption) error {
	if len(options) > 0 {
		return errGrpcOptions
	}
	return nil
}
