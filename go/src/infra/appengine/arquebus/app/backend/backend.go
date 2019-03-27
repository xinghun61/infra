// Copyright 2019 The LUCI Authors.
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

// Package backend implements the core logic of Arquebus service.
package backend

import (
	"context"

	"go.chromium.org/luci/server/router"

	"infra/appengine/arquebus/app/backend/model"
)

// InstallHandlers installs TaskQueue handlers into a given task queue.
func InstallHandlers(r *router.Router, m router.MiddlewareChain) {
	// TODO(crbug/849469): Add TQ handlers.
}

// GetAllAssigners returns all assigners.
func GetAllAssigners(c context.Context) ([]*model.Assigner, error) {
	return model.GetAllAssigners(c)
}

// GetLiveAssigners returns all assigners that are not marked as removed.
func GetLiveAssigners(c context.Context) ([]*model.Assigner, error) {
	return model.GetLiveAssigners(c)
}

// GetAssigner returns the Assigner matching with a given ID.
func GetAssigner(c context.Context, aid string) (*model.Assigner, error) {
	return model.GetAssigner(c, aid)
}
