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

// ListRsp is the response from the 'List' RPC. It contains a list of Counters
// including their IDs and Values.
type ListRsp struct {
	Counters []Counter
}

// List returns a list of all the counters. Note that it's very poorly
// implemented! It's completely unpaged. I don't care :).
func (Example) List(c context.Context) (rsp *ListRsp, err error) {
	rds := gae.GetRDS(prod.Use(c))
	rsp = &ListRsp{}
	_, err = rds.GetAll(rds.NewQuery("Counter"), &rsp.Counters)
	if err != nil {
		return
	}
	return
}

func init() {
	mi["List"] = &endpoints.MethodInfo{
		Path: "counter",
		Desc: "Returns all of the available counters",
	}
}
