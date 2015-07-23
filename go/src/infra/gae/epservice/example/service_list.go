// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package example

import (
	"github.com/GoogleCloudPlatform/go-endpoints/endpoints"
	"github.com/luci/gae/impl/prod"
	"github.com/luci/gae/service/rawdatastore"
	"golang.org/x/net/context"
)

// ListRsp is the response from the 'List' RPC. It contains a list of Counters
// including their IDs and Values.
type ListRsp struct {
	Counters []Counter
}

// List returns a list of all the counters. Note that it's very poorly
// implemented! It's completely unpaged. I don't care :).
func (Example) List(c context.Context) (rsp *ListRsp, err error) {
	rds := rawdatastore.Get(prod.Use(c))
	rsp = &ListRsp{}
	dst := []rawdatastore.PropertyMap{}
	_, err = rds.GetAll(rds.NewQuery("Counter"), &dst)
	if err != nil {
		return
	}
	rsp.Counters = make([]Counter, len(dst))
	for i, m := range dst {
		if err = rawdatastore.GetPLS(rsp.Counters[i]).Load(m); err != nil {
			return
		}
	}
	return
}

func init() {
	mi["List"] = &endpoints.MethodInfo{
		Path: "counter",
		Desc: "Returns all of the available counters",
	}
}
