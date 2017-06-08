// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build !windows

package cipd

var versionDirs = []string{
	"/opt/cq-canary",
	"/opt/cq-stable",
	"/opt/infra-python",
	"/opt/infra-tools", // authutil cipd version file is here
	"/opt/infra-tools/.versions",
}
