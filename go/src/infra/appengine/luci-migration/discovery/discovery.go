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
	"net/http"
	"sort"
	"time"

	"golang.org/x/net/context"
	"google.golang.org/api/googleapi"

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
	buildbotBuilders := stringset.NewFromSlice(names...)

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

		q := storage.BuilderMasterFilter(c, nil, master.Name).Eq("NotOnBuildbot", false)
		err := datastore.RunBatch(c, 32, q, func(b *storage.Builder) error {
			// If we "lost" a Buildbot builder and there is no data from the LUCI builder, it may have
			// been deleted or renamed, or there was a blip in liveness signal.
			// We can't a priori distinguish between these two cases, so just store that the builder no
			// longer exists on Buildbot. Filtering these out of the LUCIIsProd percent calculation will
			// surface how many flipped builders we still need to decom, and how many existing builders
			// still need to be flipped.
			if !buildbotBuilders.Has(b.ID.Builder) {
				dsWork("mark lost Buildbot builder", b.ID.Builder, func() error {
					return d.markLostBuilder(c, b)
				})
			}
			return nil
		})
		if err != nil {
			work <- func() error { return err }
			return
		}
		buildbotBuilders.Iter(func(name string) bool {
			dsWork("register builder", name, func() error {
				return d.registerBuilder(c, master, name)
			})
			return true
		})
	})
}

func (d *Builders) markLostBuilder(c context.Context, builder *storage.Builder) error {
	return datastore.RunInTransaction(c, func(c context.Context) error {
		if err := datastore.Get(c, builder); err != nil {
			return err
		}

		// If we're already not on Buildbot, nothing to do.
		if builder.NotOnBuildbot {
			return nil
		}

		builder.NotOnBuildbot = true
		builder.Migration = storage.BuilderMigration{
			Status:       storage.StatusUnknown,
			AnalysisTime: clock.Now(c),
		}
		details := &storage.BuilderMigrationDetails{
			Parent:      datastore.KeyForObj(c, builder),
			TrustedHTML: "The builder could not be found on Buildbot so has been marked status Unknown",
		}

		return datastore.Put(c, builder, details)
	}, nil)
}

func (d *Builders) registerBuilder(c context.Context, master *config.Master, name string) error {
	builder := &storage.Builder{
		ID:             bid(master.Name, name),
		SchedulingType: master.SchedulingType,
		OS:             master.Os,
	}

	// If the builder already exists, we don't need to register it again.
	// Do update that it was [re]found on Buildbot, though.
	return datastore.RunInTransaction(c, func(c context.Context) error {
		err := datastore.Get(c, builder)
		switch {
		case err == nil:
			// Only update if the last known state was "not on Buildbot".
			if builder.NotOnBuildbot {
				builder.NotOnBuildbot = false
				return datastore.Put(c, builder)
			}
			return nil
		case err != datastore.ErrNoSuchEntity:
			return err
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
	}, nil)
}

type masterJSON struct {
	Builders map[string]struct{}
}

func (d *Builders) fetchBuilderNames(c context.Context, master *config.Master) (names []string, err error) {
	// this is inefficient, but there is no better API
	res, err := d.Buildbot.GetCompressedMasterJSON(c, &milo.MasterRequest{
		Name:        master.Name,
		NoEmulation: true,
	})
	switch apiErr, _ := err.(*googleapi.Error); {
	case apiErr != nil && apiErr.Code == http.StatusNotFound:
		// Entire master was deleted. Treat it as there are no builders.
		return nil, nil
	case err != nil:
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
