// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildstatus

import (
	"encoding/json"
	"net/http"
	"net/url"
	"regexp"
	"strconv"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"
	milo "go.chromium.org/luci/milo/api/proto"
	"go.chromium.org/luci/server/auth"

	"infra/libs/infraenv"
	buildbot "infra/monitoring/messages"
)

// AuditMiloClient wraps Milo apis that are relevant to audit.
type AuditMiloClient struct {
	BuildbotClient milo.BuildbotClient
}

// GetBuildInfo gets the details about a specifc Buildbot build via Milo.
//
// From the buildURL a master, builder and build number are extracted and used
// to ask Milo for the build's JSON.
//
// A client with the appropriate authorization is expected in the parameter c.
//
// The response is then unmarshaled using the (very thorough) structs already
// defined in the messages package.
func (c *AuditMiloClient) GetBuildInfo(ctx context.Context, buildURL string) (*buildbot.Build, error) {
	m, b, n, err := parseBuildURL(buildURL)
	if err != nil {
		return nil, err
	}

	req := &milo.BuildbotBuildRequest{Master: m, Builder: b, BuildNum: n}
	resp, err := c.BuildbotClient.GetBuildbotBuildJSON(ctx, req)
	if err != nil {
		return nil, err
	}

	bi := &buildbot.Build{}
	if err = json.Unmarshal(resp.Data, bi); err != nil {
		return nil, err
	}
	return bi, nil
}

// NewAuditMiloClient creates prpc client ready to talk to Milo.
func NewAuditMiloClient(ctx context.Context, authKind auth.RPCAuthorityKind) (*AuditMiloClient, error) {
	// TODO(robertocn): Move this (or something apropos) to luci/milo/api.
	authTransport, err := auth.GetRPCTransport(ctx, authKind)
	if err != nil {
		return nil, err
	}
	options := prpc.DefaultOptions()
	return &AuditMiloClient{milo.NewBuildbotPRPCClient(&prpc.Client{
		Host:    infraenv.ProdMiloHost,
		C:       &http.Client{Transport: authTransport},
		Options: options,
	})}, nil
}

var miloPathRX = regexp.MustCompile(
	`/buildbot/(?P<master>[^/]+)/(?P<builder>[^/]+)/(?P<buildNum>\d+)/?`)

// parseBuildURL obtains master, builder and build number from the build url.
func parseBuildURL(rawURL string) (master string, builder string, buildNum int64, err error) {
	u, err := url.Parse(rawURL)
	if err != nil {
		return
	}
	m := miloPathRX.FindStringSubmatch(u.Path)
	names := miloPathRX.SubexpNames()
	if len(m) < len(names) || m == nil {
		err = errors.Reason("The path given does not match the expected format. %s", u.Path).Err()
		return
	}
	parts := map[string]string{}
	for i, name := range names {
		if i != 0 {
			parts[name] = m[i]
		}
	}
	master, hasMaster := parts["master"]
	builder, hasBuilder := parts["builder"]
	buildNumS, hasBuildNum := parts["buildNum"]
	if !(hasMaster && hasBuilder && hasBuildNum) {
		err = errors.Reason("The path given does not match the expected format. %s", u.Path).Err()
		return
	}
	buildNumI, err := strconv.Atoi(buildNumS)
	if err != nil {
		return
	}
	buildNum = int64(buildNumI)
	return
}
