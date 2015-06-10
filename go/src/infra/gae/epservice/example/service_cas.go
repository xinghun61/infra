// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package example

import (
	"golang.org/x/net/context"
	"infra/gae/libs/wrapper"
	"infra/gae/libs/wrapper/gae"

	"github.com/GoogleCloudPlatform/go-endpoints/endpoints"
)

// CASReq is the input for the CAS RPC
type CASReq struct {
	Name string `endpoints:"required"`

	OldVal int64 `json:",string"`
	NewVal int64 `json:",string"`
}

// CAS does an atomic compare-and-swap on a counter.
func (Example) CAS(c endpoints.Context, r *CASReq) (err error) {
	success := false
	ds := wrapper.GetDS(gae.Use(context.Background(), c))
	err = ds.RunInTransaction(func(context.Context) error {
		ctr := &Counter{ID: r.Name}
		if err := ds.Get(ctr); err != nil {
			return err
		}
		if ctr.Val == r.OldVal {
			success = true
			ctr.Val = r.NewVal
			_, err := ds.Put(ctr)
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
