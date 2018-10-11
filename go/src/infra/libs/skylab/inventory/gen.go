// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package inventory

//go:generate protoc --go_out=./ common.proto
//go:generate protoc --go_out=./ connection.proto
//go:generate protoc --go_out=./ device.proto
//go:generate protoc --go_out=./ lab.proto
//go:generate protoc --go_out=./ server.proto
//go:generate protoc --go_out=./ stable_versions.proto
