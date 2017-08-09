// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"net/url"
	"strconv"
	"time"

	"go.chromium.org/gae/service/datastore"

	"infra/appengine/test-results/model"
)

// URLParams represents the query string parameters in a HTTP GET
// request to the "/testfile" endpoint.
type URLParams struct {
	Master            string
	Builder           string
	Name              string
	TestType          string
	BuildNumber       *int
	OrderBuildNumbers bool // Whether to order build numbers by latest.
	Before            time.Time
	NumFiles          *int32
	TestListJSON      bool
	Key               string // base64 encoded key.
	Callback          string // Name of callback function.
}

// NewURLParams creates a URLParams from the supplied url.Values.
func NewURLParams(m url.Values) (URLParams, error) {
	u := URLParams{}
	u.Master = m.Get("master")
	u.Builder = m.Get("builder")
	u.Name = m.Get("name")
	u.TestType = m.Get("testtype")

	switch m.Get("buildnumber") {
	case "":
		// Nothing to do. u.BuildNumber should be nil.
	case "latest":
		u.OrderBuildNumbers = true
	default:
		i, err := strconv.Atoi(m.Get("buildnumber"))
		if err != nil {
			return URLParams{}, err
		}
		u.BuildNumber = &i
	}

	if m.Get("before") != "" {
		tim, err := time.Parse(paramsTimeFormat, m.Get("before"))
		if err != nil {
			return URLParams{}, err
		}
		u.Before = tim
	}

	if m.Get("numfiles") != "" {
		i, err := strconv.Atoi(m.Get("numfiles"))
		if err != nil {
			return URLParams{}, err
		}
		i32 := int32(i)
		u.NumFiles = &i32
	} else {
		u.NumFiles = nil
	}

	if m.Get("testlistjson") != "" {
		u.TestListJSON = true
	}

	u.Key = m.Get("key")
	u.Callback = m.Get("callback")
	return u, nil
}

// Query creates a datastore query for the URLParams.
func (u *URLParams) Query() *datastore.Query {
	p := model.TestFileParams{
		Master:            u.Master,
		Builder:           u.Builder,
		Name:              u.Name,
		TestType:          u.TestType,
		BuildNumber:       u.BuildNumber,
		OrderBuildNumbers: u.OrderBuildNumbers,
		Before:            u.Before,
	}
	if u.NumFiles != nil {
		p.Limit = *u.NumFiles
	} else {
		p.Limit = int32(-1)
	}
	return p.Query()
}

// ShouldListFiles returns whether the URLParams is requesting a
// TestFile list, as opposed to the data in TestFile(s).
func (u *URLParams) ShouldListFiles() bool {
	return u.NumFiles != nil || u.Name == "" || u.Master == "" || u.Builder == "" ||
		u.TestType == "" || (u.BuildNumber == nil && !model.IsAggregateTestFile(u.Name))
}
