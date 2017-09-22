// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package client

import (
	"bytes"
	"compress/gzip"
	"encoding/json"

	"golang.org/x/net/context"

	"infra/monitoring/messages"

	"go.chromium.org/luci/common/logging"
	milo "go.chromium.org/luci/milo/api/proto"
)

// WithMiloBuildbot adds a milo Buildbot client instance to the context.
func WithMiloBuildbot(c context.Context, mc milo.BuildbotClient) context.Context {
	return context.WithValue(c, miloBuildbotKey, mc)
}

// GetMiloBuildbot returns the currently registered Milo Buidlbot client, or panics.
func GetMiloBuildbot(c context.Context) milo.BuildbotClient {
	v := c.Value(miloBuildbotKey)
	ret, ok := v.(milo.BuildbotClient)
	if !ok {
		panic("error reading milo buildbot service dependency")
	}
	return ret
}

// WithMiloBuildInfo adds a milo BuildInfo client instance to the context.
func WithMiloBuildInfo(c context.Context, mc milo.BuildInfoClient) context.Context {
	return context.WithValue(c, miloBuildInfoKey, mc)
}

// GetMiloBuildInfo returns the currently registered Milo BuildInfo client, or panics.
func GetMiloBuildInfo(c context.Context) milo.BuildInfoClient {
	v := c.Value(miloBuildInfoKey)
	ret, ok := v.(milo.BuildInfoClient)
	if !ok {
		panic("error reading milo buildinfo service dependency")
	}
	return ret
}

func (r *reader) Build(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error) {
	bbClient := GetMiloBuildbot(ctx)

	req := &milo.BuildbotBuildRequest{Master: master.Name(), Builder: builder, BuildNum: buildNum}
	resp, err := bbClient.GetBuildbotBuildJSON(ctx, req)
	if err != nil {
		logging.Errorf(ctx, "error getting build %s/%s/%d: %v", master.Name(), builder, buildNum, err)
		return nil, err
	}

	build := &messages.Build{}
	if err := json.Unmarshal(resp.Data, build); err != nil {
		return nil, err
	}

	stripUnusedFields(build)

	return build, nil
}

func stripUnusedFields(b *messages.Build) {
	b.Logs = nil

	strippedChanges := []messages.Change{}

	for _, change := range b.SourceStamp.Changes {
		change.Files = nil
		strippedChanges = append(strippedChanges, change)
	}
	b.SourceStamp.Changes = strippedChanges
}

func (r *reader) BuildExtract(ctx context.Context, master *messages.MasterLocation) (*messages.BuildExtract, error) {
	bbClient := GetMiloBuildbot(ctx)

	req := &milo.MasterRequest{Name: master.Name()}
	resp, err := bbClient.GetCompressedMasterJSON(ctx, req)
	if err != nil {
		logging.Errorf(ctx, "error getting build extract for %s: %v", master.Name(), err)
		return nil, err
	}

	gzbs := bytes.NewBuffer(resp.Data)
	gsr, err := gzip.NewReader(gzbs)
	if err != nil {
		return nil, err
	}

	dec := json.NewDecoder(gsr)
	ret := &messages.BuildExtract{}
	if err := dec.Decode(ret); err != nil {
		return nil, err
	}

	return ret, nil
}
