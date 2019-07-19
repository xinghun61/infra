// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package registry

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"strings"

	"go.chromium.org/luci/common/errors"
)

// Error is returned by Registry API on errors.
//
// See https://docs.docker.com/registry/spec/api/#errors
type Error struct {
	StatusCode int    `json:"-"` // HTTP status code
	RawError   string `json:"-"` // set if failed to unmarshal the response body
	Errors     []struct {
		Code    string `json:"code"`
		Message string `json:"message"`
	}
}

// Error implements 'error' interface.
func (e *Error) Error() string {
	b := strings.Builder{}
	fmt.Fprintf(&b, "HTTP %d - ", e.StatusCode)
	if e.RawError != "" {
		b.WriteString(e.RawError)
	} else {
		for idx, err := range e.Errors {
			if idx != 0 {
				b.WriteString("; ")
			}
			fmt.Fprintf(&b, "%s: %s", err.Code, err.Message)
		}
	}
	return b.String()
}

// maybeRegistryError extracts an error message from the Docker Registry
// response by converting it to *Error if necessary.
func maybeRegistryError(resp *http.Response, body []byte) error {
	if resp.StatusCode == 200 {
		return nil
	}
	rr := &Error{StatusCode: resp.StatusCode}
	if err := json.Unmarshal(body, rr); err != nil {
		rr.RawError = string(body) // e.g. HTTP 502 page
	}
	return rr
}

// sendJSONRequest makes a request and parses the body (as JSON) into `out`.
//
// Additionally returns the raw response body and already closed http.Response
// object (to examine response code and headers).
//
// Returns errors on non-200 responses. They are actually annotated *Error
// instances.
func sendJSONRequest(ctx context.Context, req *http.Request, out interface{}) (resp *http.Response, body []byte, err error) {
	req = req.WithContext(ctx)
	resp, err = http.DefaultClient.Do(req)
	if err != nil {
		err = errors.Annotate(err, "HTTP call failed").Err()
		return
	}
	defer resp.Body.Close()
	body, err = ioutil.ReadAll(resp.Body)
	if err != nil {
		err = errors.Annotate(err, "failed to read HTTP response body").Err()
		return
	}
	if err = maybeRegistryError(resp, body); err != nil {
		err = errors.Annotate(err, "docker registry returned an error").Err()
		return
	}
	if out != nil {
		if err = json.Unmarshal(body, out); err != nil {
			err = errors.Annotate(err, "failed to unmarshal HTTP response body").Err()
		}
	}
	return
}
