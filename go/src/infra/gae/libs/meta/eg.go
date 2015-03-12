// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package meta

import (
	"appengine/datastore"

	"infra/gae/libs/context"
	"infra/libs/errors"
)

var mark = errors.MakeMarkFn("eg")

// EntityGroupMeta is the model corresponding to the __entity_group__ model in
// appengine. You shouldn't need to use this struct directly, but instead should
// use GetEntityGroupVersion.
type EntityGroupMeta struct {
	_kind string `datastore:"-" goon:"kind,__entity_group__"`

	ID     int64          `datastore:"-" goon:"id"`
	Parent *datastore.Key `datastore:"-" goon:"parent"`

	Version int64 `datastore:"__version__"`
}

// GetEntityGroupVersion returns the entity group version for the entity group
// containing root. If the entity group doesn't exist, this function will return
// zero and a nil error.
func GetEntityGroupVersion(c context.SingleReadWriter, root *datastore.Key) (int64, error) {
	for root.Parent() != nil {
		root = root.Parent()
	}
	egm := &EntityGroupMeta{ID: 1, Parent: root}
	err := c.Get(egm)
	if err != datastore.ErrNoSuchEntity {
		err = mark(err)
	} else {
		// this is OK for callers. The version of the entity group is effectively 0
		// in this case.
		err = nil
	}
	return egm.Version, err
}
