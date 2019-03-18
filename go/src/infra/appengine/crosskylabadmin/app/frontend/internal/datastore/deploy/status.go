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

// Package deploy provides functions to store deployment status in datastore.
package deploy

import (
	"context"
	"infra/appengine/crosskylabadmin/api/fleet/v1"

	"github.com/google/uuid"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
)

// Status stores status of in-flight or completed deployment attempts.
type Status struct {
	// Specifies whether this deploy attempt is considered complete.
	IsFinal   bool
	ChangeURL string
	Status    fleet.GetDeploymentStatusResponse_Status
	// Reason for an unsuccessful deployment status.
	Reason string
	// ID of the skylab task for deployment.
	TaskID string
}

// GetStatus gets status for deployment attempt with given ID.
func GetStatus(ctx context.Context, ID string) (*Status, error) {
	e := &entity{ID: ID}
	if err := datastore.Get(ctx, e); err != nil {
		return nil, errors.Annotate(err, "get deploystatus").Err()
	}
	return &e.Status, nil
}

// PutStatus save the status of a new deployment attempt.
//
// This function returns a new unique ID of this deployment attempt.
func PutStatus(ctx context.Context, status *Status) (string, error) {
	id := uuid.New().String()
	if err := UpdateStatus(ctx, id, status); err != nil {
		return "", errors.Annotate(err, "put").Err()
	}
	return id, nil
}

// UpdateStatus updates the status of a deployment attempt.
func UpdateStatus(ctx context.Context, id string, status *Status) error {
	err := datastore.Put(ctx, &entity{
		ID:     id,
		Status: *status,
	})
	if err != nil {
		return errors.Annotate(err, "deploystatus updapte").Err()
	}
	return nil
}

type entity struct {
	_kind string `gae:"$kind,deployStatus"`
	// ID is the unique deploy attempt ID.
	ID string `gae:"$id"`
	Status
}
