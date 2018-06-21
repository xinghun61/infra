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
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
)

// taskerServerImpl implements the fleet.TaskerServer interface.
type taskerServerImpl struct {
	swarmingClientFactory
}

func (*taskerServerImpl) TriggerRepairOnIdle(context.Context, *fleet.TriggerRepairOnIdleRequest) (resp *fleet.TaskerTasksResponse, err error) {
	defer func() {
		err = grpcfyRawErrors(err)
	}()

	return nil, status.Errorf(codes.Unimplemented, "Not Implemented")
}

func (*taskerServerImpl) TriggerRepairOnRepairFailed(context.Context, *fleet.TriggerRepairOnRepairFailedRequest) (resp *fleet.TaskerTasksResponse, err error) {
	defer func() {
		err = grpcfyRawErrors(err)
	}()

	return nil, status.Errorf(codes.Unimplemented, "Not Implemented")
}

func (*taskerServerImpl) EnsureBackgroundTasks(context.Context, *fleet.EnsureBackgroundTasksRequest) (resp *fleet.TaskerTasksResponse, err error) {
	defer func() {
		err = grpcfyRawErrors(err)
	}()

	return nil, status.Errorf(codes.Unimplemented, "Not Implemented")
}
