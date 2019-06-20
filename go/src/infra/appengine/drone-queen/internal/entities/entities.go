// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package entities contains datastore entity kinds.
package entities

import (
	"context"
	"time"

	"go.chromium.org/gae/service/datastore"
)

// DUTID is a DUT ID.
type DUTID string

// DroneID is a drone ID.
type DroneID string

const (
	// DUTKind is the datastore entity kind for DUT entities.
	DUTKind string = "DUT"
	// DroneKind is the datastore entity kind for drone entities.
	DroneKind string = "Drone"

	// AssignedDroneField is a field name for queries.
	AssignedDroneField = "AssignedDrone"
	// DrainingField is a field name for queries.
	DrainingField = "Draining"
)

// DUTGroupKey returns a key to be used for all DUT entities.  This is
// used to form an entity group for DUT queries.
func DUTGroupKey(ctx context.Context) *datastore.Key {
	return datastore.MakeKey(ctx, "DUTGroup", "default")
}

// DUT is a datastore entity that tracks a DUT.
type DUT struct {
	_kind         string         `gae:"$kind,DUT"`
	ID            DUTID          `gae:"$id"`
	Group         *datastore.Key `gae:"$parent"`
	AssignedDrone DroneID
	Draining      bool
}

// Equal implements equality.
func (d DUT) Equal(v DUT) bool {
	if d.Group == nil {
		return d == v
	}
	if v.Group == nil {
		return false
	}
	if !d.Group.Equal(v.Group) {
		return false
	}
	d.Group = v.Group
	return d == v
}

// Drone is a datastore entity that tracks a drone.
type Drone struct {
	_kind      string  `gae:"$kind,Drone"`
	ID         DroneID `gae:"$id"`
	Expiration time.Time
}

// Equal implements equality.
func (d Drone) Equal(v Drone) bool {
	return d == v
}
