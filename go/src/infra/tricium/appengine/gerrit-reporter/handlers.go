// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the gerrit-reporter module.
package handlers

import (
	"net/http"
)

func init() {
	http.HandleFunc("/gerrit-reporter/queue", queueHandler)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Process request and report event to Gerrit
}
