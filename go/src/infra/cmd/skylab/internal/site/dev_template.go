// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build dev

// This file is intended for overriding environment values in this package when building for local testing.
//
//   go build -tags='dev'
//
// You can copy this file to dev.go and edit it.

package site

import "go.chromium.org/luci/grpc/prpc"

func init() {
	if false { // Change this to true.
		Dev.AdminService = "0.0.0.0:8082"
		Prod = Dev
		DefaultPRPCOptions = &prpc.Options{Insecure: true}
	}
}
