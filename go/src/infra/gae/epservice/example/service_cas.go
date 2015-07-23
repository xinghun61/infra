// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package example

import (
	"github.com/GoogleCloudPlatform/go-endpoints/endpoints"
	"github.com/luci/gae/impl/prod"
	rdsS "github.com/luci/gae/service/rawdatastore"
	"golang.org/x/net/context"
)

// CASReq is the input for the CAS RPC
type CASReq struct {
	Name string `endpoints:"required"`

	OldVal int64 `json:",string"`
	NewVal int64 `json:",string"`
}

// CAS does an atomic compare-and-swap on a counter.
func (Example) CAS(c context.Context, r *CASReq) (err error) {
	success := false
	c = prod.Use(c)
	err = rdsS.Get(c).RunInTransaction(func(c context.Context) error {
		rds := rdsS.Get(c)
		key := rds.NewKey("Counter", r.Name, 0, nil)
		ctr := &Counter{}
		pls := rdsS.GetPLS(ctr)
		if err := rds.Get(key, pls); err != nil {
			return err
		}
		if ctr.Val == r.OldVal {
			success = true
			ctr.Val = r.NewVal
			_, err := rds.Put(key, pls)
			return err
		}
		success = false
		return nil
	}, nil)
	if err == nil && !success {
		err = endpoints.ConflictError
	}
	return
}

func init() {
	mi["CAS"] = &endpoints.MethodInfo{
		Path: "counter/{Name}/cas",
		Desc: "Compare and swap a counter value",
	}
}
