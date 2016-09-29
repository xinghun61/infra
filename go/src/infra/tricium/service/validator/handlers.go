// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the validator module.
package handlers

import (
	"net/http"

	"infra/tricium/service/common"
)

func init() {
	http.HandleFunc("/validate", validateHandler)
}

func validateHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add validation code.
	// This handler should validate the provided config (project and/or service),
	// get the service config if needed from luci-config, merge configs, validate
	// the merged config. Return merged config together with validation results
	// in the response.
	d := map[string]interface{}{
		"Msg": "Status of the validator ...",
	}
	common.ShowBasePage(w, d)
}
