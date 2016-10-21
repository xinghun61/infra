// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package buildextract implements a HTTP client for the Chrome
// build extracts API.
//
// Example:
//
//   c := buildextract.NewClient(http.DefaultClient)
//   data, err := c.GetMasterJSON("chromium.mac")
//   // Error check elided.
//   io.Copy(os.Stdout, data)
//   data.Close()
//
package buildextract

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"github.com/golang/protobuf/proto"
	"github.com/luci/luci-go/grpc/prpc"
	milo "github.com/luci/luci-go/milo/api/proto"
	"golang.org/x/net/context"
)

// BaseURL is the base URL of the Milo API.
const BaseURL = "luci-milo.appspot.com"

// StatusError is returned when the HTTP roundtrip succeeds,
// but the response's status code is not http.StatusOK.
type StatusError struct {
	StatusCode int
	Status     string
	Body       []byte
}

func (e *StatusError) Error() string {
	return fmt.Sprintf("buildextract: response status code: %d", e.StatusCode)
}

// Interface is the methods that a buildextract client should provide.
//
// See Client for an implementation of this interface that
// communicates with the live service.
// See TestingClient for a client that can be used in external package tests.
type Interface interface {
	GetMasterJSON(ctx context.Context, master string) (io.ReadCloser, error)
	GetBuildsJSON(ctx context.Context, builder, master string, numBuilds int) (*BuildsData, error)
}

var _ Interface = (*Client)(nil)

// Client is the PRPC client and configuration used to make requests.
// Safe for concurrent use.
type Client struct {
	pc PRPCClient
}
type PRPCClient interface {
	Call(ctx context.Context, serviceName, methodName string, in, out proto.Message, opts ...grpc.CallOption) error
}

// NewClient returns a Client initialized with the supplied
// http.Client. The returned client is ready to make requests to the API.
func NewClient(c *http.Client) *Client {
	return &Client{
		pc: &prpc.Client{
			C:    c,
			Host: BaseURL,
		},
	}

}

// GetMasterJSON returns the masters data as JSON for the supplied arguments.
//
// If the returned error is non-nil, the caller is responsible for
// closing the retured io.ReadCloser.
func (c *Client) GetMasterJSON(ctx context.Context, master string) (io.ReadCloser, error) {
	req := &milo.MasterRequest{Name: master}
	rsp := &milo.CompressedMasterJSON{}
	err := c.pc.Call(ctx, "milo.Buildbot", "GetCompressedMasterJSON", req, rsp)
	if err != nil {
		if code := grpc.Code(err); code == codes.NotFound {
			return nil, &StatusError{
				StatusCode: http.StatusNotFound,
				Body:       []byte("not found"),
			}
		}
		return nil, err
	}
	return gzip.NewReader(bytes.NewReader(rsp.Data))
}

type Build struct {
	Steps []struct {
		Name string `json:"name"`
	} `json:"steps"`
}

type BuildsData struct {
	Builds []Build `json:"builds"`
}

// GetBuildsJSON returns the builds data as JSON for the supplied
// arguments.
//
// If the returned error is non-nil, the caller is responsible for
// closing the retured io.ReadCloser.
func (c *Client) GetBuildsJSON(ctx context.Context, builder, master string, numBuilds int) (*BuildsData, error) {
	req := &milo.BuildbotBuildsRequest{
		Master:         master,
		Builder:        builder,
		Limit:          int32(numBuilds),
		IncludeCurrent: false,
	}
	rsp := &milo.BuildbotBuildsJSON{}
	err := c.pc.Call(ctx, "milo.Buildbot", "GetBuildbotBuildsJSON", req, rsp)
	if err != nil {
		if code := grpc.Code(err); code == codes.NotFound {
			return nil, &StatusError{
				StatusCode: http.StatusNotFound,
				Body:       []byte("not found"),
			}
		}
		return nil, err
	}

	result := &BuildsData{}
	result.Builds = make([]Build, len(rsp.Builds))
	for i, b := range rsp.Builds {
		err := json.Unmarshal(b.Data, &(result.Builds[i]))
		if err != nil {
			return nil, err
		}
	}
	return result, nil
}
