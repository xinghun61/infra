// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

// State holds shared state between handlers.
type State struct {
	selfURL       string
	tokenFile     string
	tokenCallback string
}

// New creates a new handlers State container.
func New(url, tokenFile, tokenCallback string) *State {
	return &State{
		selfURL:       url,
		tokenFile:     tokenFile,
		tokenCallback: tokenCallback,
	}
}
