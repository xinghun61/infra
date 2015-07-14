// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package meta

import (
	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/errors"

	"infra/gae/libs/gae"
	"infra/gae/libs/gae/helper"
)

var mark = errors.MakeMarkFn("eg")

// EntityGroupMeta is the model corresponding to the __entity_group__ model in
// appengine. You shouldn't need to use this struct directly, but instead should
// use GetEntityGroupVersion.
type EntityGroupMeta struct {
	Version int64 `gae:"__version__"`
}

// GetEntityGroupVersion returns the entity group version for the entity group
// containing root. If the entity group doesn't exist, this function will return
// zero and a nil error.
func GetEntityGroupVersion(c context.Context, root gae.DSKey) (int64, error) {
	for root.Parent() != nil {
		root = root.Parent()
	}
	rds := gae.GetRDS(c)
	egm := &EntityGroupMeta{}
	err := rds.Get(rds.NewKey("__entity_group__", "", 1, root), helper.GetPLS(egm))
	ret := egm.Version
	if err == gae.ErrDSNoSuchEntity {
		// this is OK for callers. The version of the entity group is effectively 0
		// in this case.
		err = nil
	}
	return ret, err
}
