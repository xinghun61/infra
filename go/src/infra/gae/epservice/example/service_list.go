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

// ListRsp is the response from the 'List' RPC. It contains a list of Counters
// including their IDs and Values.
type ListRsp struct {
	Counters []Counter
}

// List returns a list of all the counters. Note that it's very poorly
// implemented! It's completely unpaged. I don't care :).
func (Example) List(c endpoints.Context) (rsp *ListRsp, err error) {
	ds := wrapper.GetDS(gae.Use(context.Background(), c))
	rsp = &ListRsp{}
	_, err = ds.GetAll(ds.NewQuery("Counter"), &rsp.Counters)
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
