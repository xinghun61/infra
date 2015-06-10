// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package example

import (
	"golang.org/x/net/context"
	"infra/gae/libs/wrapper"
	"infra/gae/libs/wrapper/gae"
	"infra/gae/libs/wrapper/gae/commonErrors"

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
func (Example) Add(c endpoints.Context, r *AddReq) (rsp *AddRsp, err error) {
	rsp = &AddRsp{}

	ds := wrapper.GetDS(gae.Use(context.Background(), c))
	err = ds.RunInTransaction(func(context.Context) error {
		ctr := &Counter{ID: r.Name}
		if err := ds.Get(ctr); err != nil && err != commonErrors.ErrNoSuchEntityDS {
			return err
		}
		rsp.Prev = ctr.Val
		ctr.Val += r.Delta
		rsp.Cur = ctr.Val
		_, err := ds.Put(ctr)
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
