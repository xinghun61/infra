// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package migration

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"infra/monorail"
	"sort"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/sync/parallel"
	"github.com/luci/luci-go/milo/api/proto"
)

type buildbotMaster struct {
	Name           string
	SchedulingType schedulingType
	LUCIBucket     string
	Public         bool
	OS             os
}

var masters = map[string]*buildbotMaster{
	"tryserver.chromium.linux": {
		SchedulingType: tryScheduling,
		LUCIBucket:     "luci.chromium.try",
		Public:         true,
		OS:             linux,
	},
	"tryserver.chromium.win": {
		SchedulingType: tryScheduling,
		LUCIBucket:     "luci.chromium.try",
		Public:         true,
		OS:             windows,
	},
	"tryserver.chromium.mac": {
		SchedulingType: tryScheduling,
		LUCIBucket:     "luci.chromium.try",
		Public:         true,
		OS:             mac,
	},
}

func init() {
	for name, master := range masters {
		master.Name = name
	}
}

type builderDiscovery struct {
	monorail monorail.MonorailClient
	buildbot milo.BuildbotClient
}

func (d *builderDiscovery) discoverNewBuilders(c context.Context) error {
	for _, m := range masters {
		if err := d.discoverNewBuildersOf(c, m); err != nil {
			return errors.Annotate(err).Reason("could not discover builders in master %(master)s").
				D("master", m.Name).
				Err()
		}
	}
	return nil
}

func (d *builderDiscovery) discoverNewBuildersOf(c context.Context, master *buildbotMaster) error {
	logging.Infof(c, "%s: discovering new builders", master.Name)

	// Fetch builder names of a master.
	names, err := d.fetchBuilderNames(c, master)
	if err != nil {
		return errors.Annotate(err).Reason("could not fetch builder names from master %(master)s").
			D("master", master).
			Err()
	}

	// Check which builders we don't know about.
	toCheck := make([]interface{}, len(names))
	for i, b := range names {
		toCheck[i] = &builder{ID: builderID{master.Name, b}}
	}

	// NOTE: There is probably an upper-bound (~500) to the number of items we can Get.
	// Right now, luci/gae won't help us here. If we ever hit a master with enough builders
	// to hit this upper-bound, we must fix this at luci/gae level.
	// In practice, we have at most 400 builders per master though.
	exists, err := datastore.Exists(c, toCheck...)
	switch {
	case err != nil:
		return err
	case exists.All():
		// We know about all builders.
		logging.Infof(c, "nothing new")
		return nil
	}

	// New builders are discovered. Register them.
	return parallel.WorkPool(10, func(work chan<- func() error) {
		for i, name := range names {
			if !exists.Get(i) {
				name := name
				work <- func() error {
					if err := d.registerBuilder(c, master, name); err != nil {
						return errors.Annotate(err).Reason("could not register builder %(builder)q").
							D("builder", &builderID{master.Name, name}).
							Err()
					}
					return nil
				}
			}
		}
	})
}

func (d *builderDiscovery) registerBuilder(c context.Context, master *buildbotMaster, name string) error {
	builder := &builder{
		ID:                     builderID{master.Name, name},
		SchedulingType:         master.SchedulingType,
		Public:                 master.Public,
		LUCIBuildbucketBucket:  master.LUCIBucket,
		LUCIBuildbucketBuilder: "LUCI " + name, // hardcode for now
		OS: master.OS,
	}
	logging.Infof(c, "registering builder %s", &builder.ID)

	// Create a Monorail issue.
	if deadline, ok := c.Deadline(); ok {
		if deadline.Sub(clock.Now(c)) < time.Minute {
			// Do not start creating a bug if we don't have much time
			return fmt.Errorf("too close to deadline")
		}
	}
	var err error
	if builder.IssueID, err = createBuilderBug(c, d.monorail, builder); err != nil {
		return errors.Annotate(err).Reason("could not create a monorail bug for builder %(ID)q").
			D("ID", &builder.ID).
			Err()
	}

	// Save.
	if err := datastore.Put(c, builder); err != nil {
		// Monorail issue was created though. Too bad.
		return err
	}
	return nil
}

type buildbotMasterJSON struct {
	Builders map[string]struct{}
}

func (d *builderDiscovery) fetchBuilderNames(c context.Context, master *buildbotMaster) (names []string, err error) {
	// this is inefficient, but there is no better API
	res, err := d.buildbot.GetCompressedMasterJSON(c, &milo.MasterRequest{Name: master.Name})
	if err != nil {
		return nil, errors.Annotate(err).Reason("GetCompressedMasterJSON RPC failed").Err()
	}
	ungzip, err := gzip.NewReader(bytes.NewReader(res.Data))
	if err != nil {
		return nil, err
	}
	defer func() {
		if e := ungzip.Close(); e != nil && err == nil {
			err = e
		}
	}()

	var masterJSON buildbotMasterJSON
	if err := json.NewDecoder(ungzip).Decode(&masterJSON); err != nil {
		return nil, err
	}

	builders := make([]string, 0, len(masterJSON.Builders))
	for b := range masterJSON.Builders {
		builders = append(builders, b)
	}
	sort.Strings(builders)
	return builders, nil
}
