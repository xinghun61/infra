// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

//go:generate go install go.chromium.org/luci/grpc/cmd/cproto
//go:generate cproto
//go:generate svcdec -type ChopsAnnouncementsServer
