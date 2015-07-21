// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"errors"
	"flag"
	"fmt"
	"io/ioutil"
	"net/http"

	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/clock"
	luciErrors "github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"golang.org/x/net/context"
)

const (
	// monitoringEndpointUserAgent is the user agent string that should be
	// supplied to acquisitions endpoint requests.
	monitoringEndpointUserAgent = "Google-Acquisitions-Storage/1.1/python"

	// protobufContentType is MIME type for a protobuf header.
	protobufContentType = "application/x-protobuf"
)

var (
	// endpointScopes are the set of OAuth2 scopes to request for the endpoint
	// client.
	endpointScopes = []string{
		auth.OAuthScopeEmail,
		"https://www.googleapis.com/auth/acquisitionsstorage",
	}
)

type endpointService interface {
	// send pushes the supplied binary blob to the endpoint proxy.
	send(context.Context, []byte) error
}

type endpointServiceImpl struct {
	endpointConfig

	client *http.Client
}

// endpointConfig is the set of configuration parameters for an endpoint client.
type endpointConfig struct {
	url string // The URL of the monitoring endpoint.

	serviceAccountJSONPath string // The path to the service account JSON file.
}

// addFlags adds the configuration's flags to the supplied FlagSet.
func (c *endpointConfig) addFlags(fs *flag.FlagSet) {
	fs.StringVar(&c.serviceAccountJSONPath, "endpoint-service-account-json", "",
		"The path to the service account JSON credentials to use for endpoint pushes.")
	fs.StringVar(&c.url, "endpoint-url", c.url,
		"The URL of the monitoring endpoint.")
}

func (c *endpointConfig) createService(ctx context.Context) (endpointService, error) {
	if c.url == "" {
		return nil, errors.New("endpoint: you must supply a monitoring endpoint")
	}

	authenticator := auth.NewAuthenticator(
		auth.Options{
			Method:                 auth.ServiceAccountMethod,
			Scopes:                 endpointScopes,
			ServiceAccountJSONPath: c.serviceAccountJSONPath,
			Logger:                 log.Get(ctx),
		})
	client, err := auth.AuthenticatedClient(auth.SilentLogin, authenticator)
	if err != nil {
		log.Errorf(log.SetError(ctx, err), "Failed to configure endpoint client.")
		return nil, errors.New("endpoint: failed to configure endpoint client")
	}

	return &endpointServiceImpl{
		endpointConfig: *c,
		client:         client,
	}, nil
}

func (s *endpointServiceImpl) send(ctx context.Context, data []byte) error {
	ctx = log.SetField(ctx, "endpointURL", s.url)
	return retryCall(ctx, "endpoint.send", func() error {
		startTime := clock.Now(ctx)

		log.Debugf(ctx, "Pushing message to endpoint.")
		req, err := http.NewRequest("POST", s.url, bytes.NewReader(data))
		if err != nil {
			log.Errorf(log.SetError(ctx, err), "Failed to create HTTP request.")
			return err
		}
		req.Header.Add("content-type", protobufContentType)
		req.Header.Add("user-agent", monitoringEndpointUserAgent)

		resp, err := s.client.Do(req)
		if err != nil {
			// Treat a client error as transient.
			log.Warningf(log.SetError(ctx, err), "Failed proxy client request.")
			return luciErrors.Transient{Err: err}
		}
		defer resp.Body.Close()

		// Read the full response body. This will enable us to re-use the
		// connection.
		bodyData, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			log.Errorf(log.SetError(ctx, err), "Error during endpoint connection.")
			return luciErrors.Transient{Err: err}
		}

		log.Fields{
			"status":        resp.Status,
			"statusCode":    resp.StatusCode,
			"headers":       resp.Header,
			"contentLength": resp.ContentLength,
			"body":          string(bodyData),
			"duration":      clock.Now(ctx).Sub(startTime),
		}.Debugf(ctx, "Received HTTP response from endpoint.")

		if resp.StatusCode == http.StatusOK && resp.StatusCode < http.StatusMultipleChoices {
			log.Debugf(ctx, "Message pushed successfully.")
			return nil
		}

		err = fmt.Errorf("http: server error (%d)", resp.StatusCode)
		if resp.StatusCode >= http.StatusInternalServerError {
			err = luciErrors.Transient{Err: err}
		}

		log.Fields{
			log.ErrorKey: err,
			"status":     resp.Status,
			"statusCode": resp.StatusCode,
		}.Warningf(ctx, "Proxy error.")
		return err
	})
}
