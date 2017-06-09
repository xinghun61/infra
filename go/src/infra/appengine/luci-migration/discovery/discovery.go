// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package discovery files bugs and registers builders in the storage.
package discovery

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

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"
)

// Builders finds and registers new builders.
type Builders struct {
	Monorail         monorail.MonorailClient
	MonorailHostname string

	Buildbot milo.BuildbotClient

	RegistrationSemaphore parallel.Semaphore // bounds parallel builder registration
}

// Discover fetches builder names of the master and registers new ones in the
// storage.
func (d *Builders) Discover(c context.Context, master *config.Master) error {
	logging.Infof(c, "discovering new builders")

	if master.SchedulingType != config.SchedulingType_TRYJOBS {
		// TODO(nodir): add support for other types of scheduling
		logging.Infof(c, "unsupported scheduling type %s", master.SchedulingType)
		return nil
	}

	// Fetch builder names of a master.
	names, err := d.fetchBuilderNames(c, master)
	if err != nil {
		return errors.Annotate(err).Reason("could not fetch builder names from master %(master)s").
			D("master", master.Name).
			Err()
	}

	// Check which builders we don't know about.
	toCheck := make([]interface{}, len(names))
	for i, b := range names {
		toCheck[i] = &storage.Builder{ID: bid(master.Name, b)}
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
	// This should always return nil.
	return parallel.FanOutIn(func(work chan<- func() error) {
		for i, name := range names {
			if !exists.Get(i) {
				name := name
				c := logging.SetField(c, "builder", name)
				work <- func() error {
					if d.RegistrationSemaphore != nil {
						d.RegistrationSemaphore.Lock()
						defer d.RegistrationSemaphore.Unlock()
					}
					logging.Infof(c, "registering builder")
					if err := d.registerBuilder(c, master, name); err != nil {
						logging.WithError(err).Errorf(c, "could not register builder")
					}
					return nil
				}
			}
		}
	})
}

func (d *Builders) registerBuilder(c context.Context, master *config.Master, name string) error {
	builder := &storage.Builder{
		ID:                     bid(master.Name, name),
		SchedulingType:         master.SchedulingType,
		LUCIBuildbucketBucket:  master.LuciBucket,
		LUCIBuildbucketBuilder: "LUCI " + name, // hardcode for now
		OS: master.Os,
	}

	// Create a Monorail issue.
	if deadline, ok := c.Deadline(); ok {
		if deadline.Sub(clock.Now(c)) < time.Minute {
			// Do not start creating a bug if we don't have much time
			return fmt.Errorf("too close to deadline")
		}

	}
	builder.IssueID.Hostname = d.MonorailHostname
	builder.IssueID.Project = monorailProject
	var err error
	if builder.IssueID.ID, err = createBuilderBug(c, d.Monorail, builder); err != nil {
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

type masterJSON struct {
	Builders map[string]struct{}
}

func (d *Builders) fetchBuilderNames(c context.Context, master *config.Master) (names []string, err error) {
	// this is inefficient, but there is no better API
	res, err := d.Buildbot.GetCompressedMasterJSON(c, &milo.MasterRequest{Name: master.Name})
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

	var masterJSON masterJSON
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

func bid(master, builder string) storage.BuilderID {
	return storage.BuilderID{Master: master, Builder: builder}
}
