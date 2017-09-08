// Copyright 2017 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package app

import (
	"fmt"
	"net/http"
	"net/url"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

	"infra/appengine/luci-migration/analysis"
	"infra/appengine/luci-migration/common"
	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"
)

// cronAnalyzeBuilders enqueues a push task for each not-migrated-yet builder.
func cronAnalyzeBuilders(c *router.Context) error {
	var builders []*storage.Builder
	q := datastore.NewQuery(storage.BuilderKind).
		Lt("Migration.Status", storage.StatusMigrated)
	if err := datastore.GetAll(c.Context, q, &builders); err != nil {
		return err
	}

	tasks := make([]*taskqueue.Task, len(builders))
	for i, b := range builders {
		values := url.Values{}
		values.Set("builder", b.ID.String())
		tasks[i] = taskqueue.NewPOSTTask("/internal/task/analyze-builder/"+common.PathEscape(b.ID.String()), values)
		tasks[i].Delay = time.Duration(mathrand.Int(c.Context)%30) * time.Minute
		tasks[i].RetryCount = 2
	}
	if err := taskqueue.Add(c.Context, "analyze-builders", tasks...); err != nil {
		return err
	}
	logging.Infof(c.Context, "enqueued %d tasks", len(tasks))
	return nil
}

// handleAnalyzeBuilder runs analysis for one builder and persists results
// to datastore.
func handleAnalyzeBuilder(c *router.Context) error {
	// Standard push task timeout is 10min.
	c.Context, _ = context.WithDeadline(c.Context, clock.Now(c.Context).Add(10*time.Minute))

	// Load builder
	builder := &storage.Builder{}
	if idStr := c.Request.FormValue("builder"); builder.ID.Parse(idStr) != nil {
		http.Error(c.Writer, fmt.Sprintf("invalid builder %q", idStr), http.StatusBadRequest)
		return nil
	}
	if err := datastore.Get(c.Context, builder); err != nil {
		if err == datastore.ErrNoSuchEntity {
			http.Error(c.Writer, fmt.Sprintf("builder %q not found", &builder.ID), http.StatusNotFound)
			return nil
		}
		return err
	}

	// Create buildbucket client.
	cfg, err := config.Get(c.Context)
	if err != nil {
		return err
	}
	if cfg.BuildbucketHostname == "" {
		return errors.New("buildbucket hostname is not configured")
	}
	transport, err := auth.GetRPCTransport(c.Context, auth.AsSelf)
	if err != nil {
		return errors.Annotate(err, "could not get RPC transport").Err()
	}
	httpClient := &http.Client{Transport: transport}
	bb, err := buildbucket.New(httpClient)
	if err != nil {
		return errors.Annotate(err, "could not create buildbucket client").Err()
	}
	bb.BasePath = fmt.Sprintf("https://%s/api/buildbucket/v1/", cfg.BuildbucketHostname)

	// Run analysis.
	logging.Infof(c.Context, "analyzing %q", &builder.ID)
	started := clock.Now(c.Context)
	tryjobs := analysis.Tryjobs{
		HTTP:                 httpClient,
		Buildbucket:          bb,
		MaxGroups:            analysis.DefaultMaxGroups,
		MinTrustworthyGroups: analysis.DefaultMaxGroups / 2,
		// Avoid analysing old builds.
		// They might fail for reasons that are not relevant anymore.
		MaxBuildAge: time.Hour * 24 * 7,
	}
	migration, detailsHTML, err := tryjobs.Analyze(
		c.Context,
		analysis.BucketBuilder{Bucket: "master." + builder.ID.Master, Builder: builder.ID.Builder},
		analysis.BucketBuilder{Bucket: builder.LUCIBuildbucketBucket, Builder: builder.LUCIBuildbucketBuilder},
		builder.Migration.Status,
	)
	if err != nil {
		return errors.Annotate(err, "analysis failed").Err()
	}
	logging.Infof(c.Context, "analysis finshed in %s", clock.Since(c.Context, started))
	logging.Infof(c.Context, "status: %s", migration.Status)
	logging.Infof(c.Context, "correctness: %.2f", migration.Correctness)
	logging.Infof(c.Context, "speed: %.2f", migration.Speed)

	// Persist results.
	// We intentionally store only the latest analysis report.
	// We don't intend to store historical reports.
	// If some historical information needs to be persisted, it should be saved
	// in other places, e.g. Monorail or monitoring.
	err = datastore.RunInTransaction(c.Context, func(c context.Context) error {
		if err := datastore.Get(c, builder); err != nil {
			return err
		}
		builder.Migration = *migration
		migrationDetails := &storage.BuilderMigrationDetails{
			Parent:      datastore.KeyForObj(c, builder),
			TrustedHTML: detailsHTML,
		}
		return datastore.Put(c, builder, migrationDetails)
	}, nil)
	if err != nil {
		return err
	}

	// TODO(nodir): post an update to the builder's bug if the new analysis
	// results are sufficiently different from the previous ones.
	// TODO(nodir): update tsmon speed/correctness metrics per builder
	return nil
}
