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

type miloClient struct {
	BuildBot milo.BuildbotClient
}

func (r *miloClient) Build(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error) {
	req := &milo.BuildbotBuildRequest{
		Master:            master.Name(),
		Builder:           builder,
		BuildNum:          buildNum,
		ExcludeDeprecated: true,
	}
	resp, err := r.BuildBot.GetBuildbotBuildJSON(ctx, req)
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

func (r *miloClient) BuildExtract(ctx context.Context, master *messages.MasterLocation) (*messages.BuildExtract, error) {
	req := &milo.MasterRequest{
		Name:              master.Name(),
		ExcludeDeprecated: true,
	}
	resp, err := r.BuildBot.GetCompressedMasterJSON(ctx, req)
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
