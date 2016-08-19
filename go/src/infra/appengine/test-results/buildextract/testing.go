// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildextract

import (
	"bytes"
	"io"
	"io/ioutil"
	"net/http"
)

// TestingClient is provided for use by external packages tests.
type TestingClient struct {
	// M is a map from master name to the bytes in the
	// GetMasterJSON response.
	M map[string][]byte

	// B maps a master+builder combination to the bytes in the
	// GetBuildsJSON response for the combination.
	// The keys in the outer map are the master names and the keys
	// in the inner map are the builder names.
	B map[string]map[string][]byte
}

var _ Interface = (*TestingClient)(nil)

// GetMasterJSON returns the value in c.M for the supplied master.
// If the master does not exist, the error will be StatusError with
// StatusCode set to http.StatusNotFound.
func (c *TestingClient) GetMasterJSON(master string) (io.ReadCloser, error) {
	b, ok := c.M[master]
	if !ok {
		return nil, &StatusError{
			StatusCode: http.StatusNotFound,
			Body:       []byte("not found"),
		}
	}
	return ioutil.NopCloser(bytes.NewReader(b)), nil
}

// GetBuildsJSON returns the value in c.B for the supplied master
// and builder combination. If either the master or builder key does not exist,
// the error will be StatusError with StatusCode set to
// http.StatusNotFound.
//
// WARNING: The last argument is currently unsupported and is ignored.
func (c *TestingClient) GetBuildsJSON(builder, master string, _ int) (io.ReadCloser, error) {
	m, ok := c.B[master]
	if !ok {
		return nil, &StatusError{
			StatusCode: http.StatusNotFound,
			Body:       []byte("not found"),
		}
	}
	b, ok := m[builder]
	if !ok {
		return nil, &StatusError{
			StatusCode: http.StatusNotFound,
			Body:       []byte("not found"),
		}
	}
	return ioutil.NopCloser(bytes.NewReader(b)), nil
}
