// Copyright 2018 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package app

import (
	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// checkAccess verifies that the request is from an authorized user.
//
// Servers should use checkAccess as a Prelude while handling requests to uniformly
// check access across the API.
func checkAccess(c context.Context, _ string, _ proto.Message) (context.Context, error) {
	switch allow, err := auth.IsMember(c, accessGroup); {
	case err != nil:
		return c, status.Errorf(codes.Internal, "can't check ACL - %s", err)
	case !allow:
		return c, status.Errorf(codes.PermissionDenied, "permission denied")
	}
	return c, nil
}
