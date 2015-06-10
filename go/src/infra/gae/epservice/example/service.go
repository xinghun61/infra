// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package example is an example Google Cloud Endpoints service, which is
// compatible with the automatic client generation code in infra/gae/epclient.
//
// It implements a really dumb named persistant counter.
package example

import (
	"infra/gae/libs/ephelper"

	"github.com/GoogleCloudPlatform/go-endpoints/endpoints"
)

// Example is the example service type.
type Example struct{}

var mi = ephelper.MethodInfoMap{}

var si = &endpoints.ServiceInfo{
	Name:        "dumb_counter",
	Version:     "v1",
	Description: "A hideously stupid persistant counter service.",
}

// RegisterEndpointsService allows appengine apps (and epclient's `go generate`
// functionality) to register this stupid dumb_counter service.
func RegisterEndpointsService(s *endpoints.Server) error {
	return ephelper.Register(s, Example{}, si, mi)
}
