// Copyright 2016 The Chromium Authors. All rights reserved.  Use of this source
// code is governed by a BSD-style license that can be found in the LICENSE
// file.

package tricium

//go:generate go install go.chromium.org/gae/tools/proto-gae
//go:generate go install go.chromium.org/luci/grpc/cmd/cproto
//go:generate cproto
//go:generate proto-gae -type ProjectConfig -type ServiceConfig -type Acl -type Data_File
