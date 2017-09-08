// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"net/http"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/server/auth"
)

// TODO(robertocn): Move this to the gitiles library.
const (
	gitilesScope = "https://www.googleapis.com/auth/gerritcodereview"
)

type gerritClientInterface interface {
	GetChangeDetails(context.Context, string, []string) (*gerrit.Change, error)
	ChangeQuery(context.Context, gerrit.ChangeQueryRequest) ([]*gerrit.Change, bool, error)
}

type gitilesClientInterface interface {
	LogForward(context.Context, string, string, string) ([]gitiles.Commit, error)
	Log(context.Context, string, string, int) ([]gitiles.Commit, error)
}

// getGitilesClient creates a new gitiles client bound to a new http client
// that is bound to an authenticated transport.
func getGitilesClient(ctx context.Context) (*gitiles.Client, error) {
	httpClient, err := getAuthenticatedHTTPClient(ctx)
	if err != nil {
		return nil, err
	}
	return &gitiles.Client{Client: httpClient}, nil
}

// TODO(robertocn): move this into a dedicated file for authentication, and
// accept a list of scopes to make this function usable for communicating for
// different systems.
func getAuthenticatedHTTPClient(ctx context.Context) (*http.Client, error) {
	t, err := auth.GetRPCTransport(ctx, auth.AsSelf, auth.WithScopes(gitilesScope))
	if err != nil {
		return nil, err
	}
	return &http.Client{Transport: t}, nil
}
