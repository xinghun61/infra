// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package registry

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"sync"
	"time"

	"golang.org/x/oauth2"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
)

// authService encapsulates communication with Docker authorization service as
// described in https://docs.docker.com/registry/spec/auth/token/.
type authService struct {
	realm   string             // e.g. "https://gcr.io/token"
	service string             // e.g. "gcr.io"
	ts      oauth2.TokenSource // if non-nil, send OAuth tokens

	m      sync.RWMutex           // protects 'tokens' and the token minting process
	tokens map[string]cachedToken // full scope name => token that has it
}

// cachedToken is a docker registry authentication token.
//
// For GCR we get it in exchange for OAuth2 access token.
type cachedToken struct {
	token  string    // actual token as base64 string
	expiry time.Time // when it expires
}

// usable is true if the token appears to be valid.
func (t *cachedToken) usable() bool {
	return t.token != "" || time.Now().Add(30*time.Second).Before(t.expiry)
}

// authorizeRequest appends an authorization header to the request, getting it
// first if necessary.
//
// 'repo' is something like 'library/ubuntu' and scopes is 'pull,push' or a
// subset of thereof.
func (s *authService) authorizeRequest(ctx context.Context, r *http.Request, repo, scopes string) error {
	fullScope := fmt.Sprintf("repository:%s:%s", repo, scopes)

	s.m.RLock()
	tok := s.tokens[fullScope]
	s.m.RUnlock()

	if !tok.usable() {
		s.m.Lock()
		defer s.m.Unlock()

		if tok = s.tokens[fullScope]; !tok.usable() {
			var err error
			tok, err = s.mintAuthToken(ctx, fullScope)
			if err != nil {
				return err
			}
			if s.tokens == nil {
				s.tokens = make(map[string]cachedToken, 1)
			}
			s.tokens[fullScope] = tok
		}
	}

	r.Header.Set("Authorization", "Bearer "+tok.token)
	return nil
}

// mintAuthToken gets a docker registry token from an auth service.
func (s *authService) mintAuthToken(ctx context.Context, scope string) (cachedToken, error) {
	logging.Debugf(ctx, "Minting docker registry auth token for %s %s...", s.service, scope)

	params := url.Values{
		"scope":   {scope},
		"service": {s.service},
	}
	req, _ := http.NewRequest("GET", fmt.Sprintf("%s?%s", s.realm, params.Encode()), nil)
	req.Header.Set("Accept", "application/json")

	// s.ts is used with gcr.io. gcr.io knows how to convert OAuth2 tokens into
	// docker registry tokens. For other registries we request anonymous token.
	if s.ts != nil {
		oauthTok, err := s.ts.Token()
		if err != nil {
			return cachedToken{}, errors.Annotate(err, "failed to grab OAuth2 token").Err()
		}
		oauthTok.SetAuthHeader(req)
	}

	var parsed struct {
		ExpiresIn int    `json:"expires_in"`
		Token     string `json:"token"`
	}
	if _, _, err := sendJSONRequest(ctx, req, &parsed); err != nil {
		return cachedToken{}, errors.Annotate(err, "failed to call authorization service").Err()
	}
	if parsed.ExpiresIn == 0 {
		parsed.ExpiresIn = 60 // the default, per the doc
	}

	return cachedToken{
		token:  parsed.Token,
		expiry: time.Now().Add(time.Duration(parsed.ExpiresIn) * time.Second),
	}, nil
}
