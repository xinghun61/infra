// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package example

import (
	"golang.org/x/net/context"
	"infra/gae/libs/gae"
	"infra/gae/libs/gae/prod"

	"github.com/GoogleCloudPlatform/go-endpoints/endpoints"
)

// AddReq describes the input parameters to the 'Add' RPC. Name is required,
// which makes it show up in the REST path, and Delta will be encoded in the
// request body as JSON.
type AddReq struct {
	Name string `endpoints:"required"`

	Delta int64 `json:",string"`
}

// AddRsp describes the return value from the 'Add' RPC. Prev is the previous
// value, and Cur is the post-increment value.
type AddRsp struct {
	Prev int64 `json:",string"`
	Cur  int64 `json:",string"`
}

// Add adds a value to the current counter, and returns the old+new values. It
// may cause a counter to come into existance.
func (Example) Add(c context.Context, r *AddReq) (rsp *AddRsp, err error) {
	rsp = &AddRsp{}

	c = prod.Use(c)
	err = gae.GetRDS(c).RunInTransaction(func(c context.Context) error {
		rds := gae.GetRDS(c)
		ctr := &Counter{}
		key := rds.NewKey("Counter", r.Name, 0, nil)
		if err := rds.Get(key, ctr); err != nil && err != gae.ErrDSNoSuchEntity {
			return err
		}
		rsp.Prev = ctr.Val
		ctr.Val += r.Delta
		rsp.Cur = ctr.Val
		_, err := rds.Put(key, ctr)
		return err
	}, nil)
	return
}

func init() {
	mi["Add"] = &endpoints.MethodInfo{
		Path: "counter/{Name}",
		Desc: "Add an an amount to a particular counter",
	}
}
