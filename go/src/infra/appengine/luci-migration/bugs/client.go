// Copyright 2017 The LUCI Authors.
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

package bugs

import (
	"fmt"
	"net/http"

	"infra/monorail"
	"infra/monorail/monorailtest"
)

func NewClient(httpClient *http.Client, hostname string) monorail.MonorailClient {
	return monorail.NewEndpointsClient(
		httpClient,
		fmt.Sprintf("https://%s/_ah/api/monorail/v1", hostname),
	)
}

// ClientFactory creates a monorail client by a hostname.
type ClientFactory func(hostname string) monorail.MonorailClient

// DefaultFactory returns a factory that creates an endpoints-based Monorail
// client.
func DefaultFactory(transport http.RoundTripper) ClientFactory {
	return func(hostname string) monorail.MonorailClient {
		return NewClient(&http.Client{Transport: transport}, hostname)
	}
}

// ForwardingFactory returns a factory that creates a client based on the
// given server implementation. The factory ignores the hostname parameter.
func ForwardingFactory(server monorail.MonorailServer) ClientFactory {
	return func(hostname string) monorail.MonorailClient {
		// ignore hostname
		return monorailtest.NewClient(server)
	}
}
