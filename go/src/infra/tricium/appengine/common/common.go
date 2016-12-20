// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package common implements common functionality for the Tricium service modules.
package common

import (
	"net/http"

	"golang.org/x/net/context"

	"google.golang.org/appengine/log"
)

// Entity encapsulates a byte slice for storing in datastore.
type Entity struct {
	Value []byte
}

// ReportServerError reports back a server error (http code 500).
func ReportServerError(ctx context.Context, w http.ResponseWriter, err error) {
	log.Errorf(ctx, "Error: %v", err)
	http.Error(w, "An internal server error occured. We are working on it ;)",
		http.StatusInternalServerError)
}
