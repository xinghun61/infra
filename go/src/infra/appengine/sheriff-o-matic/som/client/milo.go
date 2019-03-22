// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package client

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"time"

	"golang.org/x/net/context"

	"infra/monitoring/messages"

	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/common/logging"
	milo "go.chromium.org/luci/milo/api/proto"
)

type miloClient struct {
	BuildBot milo.BuildbotClient
}

func miloBuildCacheKey(master *messages.MasterLocation, builder string, buildNum int64) string {
	return fmt.Sprintf("miloBuild:%s:%s:%d", master.String(), builder, buildNum)
}

func (r *miloClient) cachedBuild(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) ([]byte, error) {
	cacheKey := miloBuildCacheKey(master, builder, buildNum)
	item, err := memcache.GetKey(ctx, cacheKey)
	if err != nil && err != memcache.ErrCacheMiss {
		return nil, err
	}

	var b []byte
	if err == memcache.ErrCacheMiss {
		b, err = r.uncachedBuild(ctx, master, builder, buildNum)
		if err != nil {
			return nil, err
		}

		item = memcache.NewItem(ctx, cacheKey).SetValue(b).SetExpiration(30 * time.Minute)
		err = memcache.Set(ctx, item)
	}

	if err != nil {
		return nil, err
	}

	return item.Value(), nil
}

func (r *miloClient) uncachedBuild(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) ([]byte, error) {
	req := &milo.BuildbotBuildRequest{
		Master:            master.Name(),
		Builder:           builder,
		BuildNum:          buildNum,
		ExcludeDeprecated: true,
	}
	logging.Debugf(ctx, "Getting build %s/%s/%d", master.Name(), builder, buildNum)
	resp, err := r.BuildBot.GetBuildbotBuildJSON(ctx, req)
	if err != nil {
		logging.Errorf(ctx, "Error getting build %s/%s/%d: %v", master.Name(), builder, buildNum, err)
		return nil, err
	}
	return resp.Data, nil
}

func (r *miloClient) Build(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error) {
	data, err := r.cachedBuild(ctx, master, builder, buildNum)
	if err != nil {
		return nil, err
	}
	build := &messages.Build{}
	if err := json.Unmarshal(data, build); err != nil {
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
	logging.Debugf(ctx, "Getting compressed master json for %s", master.Name())
	resp, err := r.BuildBot.GetCompressedMasterJSON(ctx, req)
	if err != nil {
		logging.Errorf(ctx, "Error getting compressed master json for %s: %v", master.Name(), err)
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
