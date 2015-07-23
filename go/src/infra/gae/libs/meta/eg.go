// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package meta

import (
	rdsS "github.com/luci/gae/service/rawdatastore"
	"github.com/luci/luci-go/common/errors"
	"golang.org/x/net/context"
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
func GetEntityGroupVersion(c context.Context, root rdsS.Key) (int64, error) {
	for root.Parent() != nil {
		root = root.Parent()
	}
	rds := rdsS.Get(c)
	egm := &EntityGroupMeta{}
	err := rds.Get(rds.NewKey("__entity_group__", "", 1, root), rdsS.GetPLS(egm))
	ret := egm.Version
	if err == rdsS.ErrNoSuchEntity {
		// this is OK for callers. The version of the entity group is effectively 0
		// in this case.
		err = nil
	}
	return ret, err
}
