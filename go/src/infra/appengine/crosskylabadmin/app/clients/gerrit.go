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

	gerritapi "go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
)

func NewGerritClient(c context.Context, host string) (gerrit.GerritClient, error) {
	// gerrit service is not part of LUCI stack, so there is no way to forward
	// our caller's credentials to the gerrit service (See doc for auth.AsUser).
	t, err := auth.GetRPCTransport(c, auth.AsSelf, auth.WithScopes(gitiles.OAuthScope))
	if err != nil {
		return nil, errors.Annotate(err, "failed to get RPC transport").Err()
	}

	return gerritapi.NewRESTClient(&http.Client{Transport: t}, host, true)
}
