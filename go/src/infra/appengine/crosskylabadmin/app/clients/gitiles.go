// Copyright 2018 The LUCI Authors.
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

package clients

import (
	"net/http"

	authclient "go.chromium.org/luci/auth"
	gitilesapi "go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
)

// NewGitilesClient returns a new gitiles client.
//
// This function is intended to be used within the context of an RPC to this
// app. The returned gitiles client forwards the oauth token used for the
// original RPC. In particular, this means that the original oauth credentials
// must include the gerrit OAuth 2.0 scope.
func NewGitilesClient(c context.Context, host string) (gitiles.GitilesClient, error) {
	t, err := auth.GetRPCTransport(c, auth.AsCredentialsForwarder)
	if err != nil {
		return nil, errors.Annotate(err, "failed to get RPC transport").Err()
	}
	return gitilesapi.NewRESTClient(&http.Client{Transport: t}, host, true)
}

// NewGitilesClientAsSelf returns a new gitiles client using oauth tokens for the
// current service itself.
//
// This function is intended to be used from cron calls that are not part of a
// user session. For normal RPC users, see NewGitilesClient.
func NewGitilesClientAsSelf(ctx context.Context, host string) (gitiles.GitilesClient, error) {
	t, err := auth.GetRPCTransport(ctx, auth.AsSelf, auth.WithScopes(authclient.OAuthScopeEmail, gitilesapi.OAuthScope))
	if err != nil {
		return nil, errors.Annotate(err, "new gitiles client as self").Err()
	}
	return gitilesapi.NewRESTClient(&http.Client{Transport: t}, host, true)
}
