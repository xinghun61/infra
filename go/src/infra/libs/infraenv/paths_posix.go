// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build darwin linux

package infraenv

var (
	// Paths on the system where credentials are stored.
	//
	// This path is provisioned by Puppet.
	systemCredentialDirs = []string{
		"/creds/service_accounts",
	}
)
