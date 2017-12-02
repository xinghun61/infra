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
	"sort"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/milo/api/proto"

	"infra/appengine/luci-migration/bugs"
	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"
)

const monorailProject = "chromium"

// Builders finds and registers new builders.
type Builders struct {
	Monorail         bugs.ClientFactory
	MonorailHostname string

	Buildbot milo.BuildbotClient

	DatastoreOpSem parallel.Semaphore // bounds parallel datastore operations
}

// Discover fetches builder names of the master and registers new ones in the
// storage.
func (d *Builders) Discover(c context.Context, master *config.Master) error {
	logging.Infof(c, "discovering new builders")

	// Fetch builder names of a master.
	names, err := d.fetchBuilderNames(c, master)
	if err != nil {
		return errors.Annotate(err, "could not fetch builder names from master %s", master.Name).Err()
	}
	toRegister := stringset.NewFromSlice(names...)

	return parallel.FanOutIn(func(work chan<- func() error) {
		dsWork := func(title, builder string, f func() error) {
			work <- func() error {
				c := logging.SetField(c, "builder", builder)
				logging.Infof(c, "%s", title)
				if d.DatastoreOpSem != nil {
					d.DatastoreOpSem.Lock()
					defer d.DatastoreOpSem.Unlock()
				}
				if err := f(); err != nil {
					logging.WithError(err).Errorf(c, "failed to %s", title)
				}
				return nil
			}
		}

		q := storage.BuilderMasterFilter(c, nil, master.Name)
		err := datastore.RunBatch(c, 32, q, func(b *storage.Builder) error {
			if !toRegister.Del(b.ID.Builder) {
				// The Buildbot builder no longer exists. Perhaps it was migrated!
				dsWork("mark as migrated", b.ID.Builder, func() error {
					return d.markMigrated(c, b)
				})
			}
			return nil
		})
		if err != nil {
			work <- func() error { return err }
			return
		}
		toRegister.Iter(func(name string) bool {
			dsWork("register builder", name, func() error {
				return d.registerBuilder(c, master, name)
			})
			return true
		})
	})
}

func (d *Builders) markMigrated(c context.Context, builder *storage.Builder) error {
	builder.Migration = storage.BuilderMigration{
		Status: storage.StatusMigrated,
	}
	if err := bugs.PostComment(c, d.Monorail, builder); err != nil {
		return errors.Annotate(err, "could not mark the bug as fixed").Err()
	}

	// Note: if this transaction ultimately fails (rare case), we will post the
	// monorail comment again.
	return datastore.RunInTransaction(c, func(c context.Context) error {
		if err := datastore.Get(c, builder); err != nil {
			return err
		}

		builder.Migration = storage.BuilderMigration{
			Status:       storage.StatusMigrated,
			AnalysisTime: clock.Now(c),
		}
		details := &storage.BuilderMigrationDetails{
			Parent:      datastore.KeyForObj(c, builder),
			TrustedHTML: "The builder is marked as Migrated because Buildbot builder no longer exists",
		}

		return datastore.Put(c, builder, details)
	}, nil)
}

func (d *Builders) registerBuilder(c context.Context, master *config.Master, name string) error {
	builder := &storage.Builder{
		ID:                    bid(master.Name, name),
		SchedulingType:        master.SchedulingType,
		LUCIBuildbucketBucket: master.LuciBucket,
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
	if err := bugs.CreateBuilderBug(c, d.Monorail, builder); err != nil {
		return errors.Annotate(err, "could not create a monorail bug for builder %q", &builder.ID).Err()
	}

	return datastore.Put(c, builder)
}

type masterJSON struct {
	Builders map[string]struct{}
}

func (d *Builders) fetchBuilderNames(c context.Context, master *config.Master) (names []string, err error) {
	// this is inefficient, but there is no better API
	res, err := d.Buildbot.GetCompressedMasterJSON(c, &milo.MasterRequest{Name: master.Name})
	if err != nil {
		return nil, errors.Annotate(err, "GetCompressedMasterJSON RPC failed").Err()
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
