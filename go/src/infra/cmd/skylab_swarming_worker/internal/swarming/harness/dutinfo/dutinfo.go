// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package dutinfo implement loading Skylab DUT inventory info for the
// worker.
package dutinfo

import (
	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab_swarming_worker/internal/swarming"
	"infra/libs/skylab/inventory"
)

// Store holds a DUT's inventory info and adds a Close method.
type Store struct {
	DUT        *inventory.DeviceUnderTest
	original   *inventory.DeviceUnderTest
	updateFunc UpdateFunc
}

// Close updates the DUT's inventory info.  This method does nothing on
// subsequent calls.  This method is safe to call on a nil pointer.
func (s *Store) Close() error {
	if s == nil {
		return nil
	}
	if s.original == nil || s.updateFunc == nil {
		return nil
	}
	if err := s.updateFunc(s.original, s.DUT); err != nil {
		return errors.Annotate(err, "close DUT inventory").Err()
	}
	s.updateFunc, s.original = nil, nil
	return nil
}

// UpdateFunc is used to implement inventory updating for any changes
// to the loaded DUT info.
type UpdateFunc func(old, new *inventory.DeviceUnderTest) error

// Load loads the bot's DUT's info from the inventory.  This function
// returns a Store that should be closed to update the inventory with
// any changes to the info, using a supplied UpdateFunc.  If
// UpdateFunc is nil, the inventory is not updated.
func Load(b *swarming.Bot, f UpdateFunc) (*Store, error) {
	ddir, err := inventory.ReadSymlink(b.Inventory.DataDir)
	if err != nil {
		return nil, errors.Annotate(err, "load DUT host info").Err()
	}

	lab, err := inventory.LoadLab(ddir)
	if err != nil {
		return nil, errors.Annotate(err, "load DUT host info").Err()
	}
	for _, d := range lab.GetDuts() {
		c := d.GetCommon()
		if c.GetId() != b.DUTID {
			continue
		}
		return &Store{
			DUT:        d,
			original:   proto.Clone(d).(*inventory.DeviceUnderTest),
			updateFunc: f,
		}, nil
	}
	return nil, errors.Reason("load DUT inventory: %s not found", b.DUTID).Err()
}
