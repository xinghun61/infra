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

// Package analysis compares buildbucket builds on LUCI and Buildbot.
package analysis

// TODO(nodir): rewrite this implementation in SQL.

import (
	"bytes"
	"fmt"
	"net/http"
	"sync"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/luci/buildbucket"
	bbapi "go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"

	"infra/appengine/luci-migration/storage"
)

// DefaultMaxGroups is the default number of build groups to fetch.
const DefaultMaxGroups = 100
const groupFetchWorkers = 10

// Tryjobs compares LUCI and Buildbot tryjobs.
type Tryjobs struct {
	HTTP                 *http.Client
	Buildbucket          *bbapi.Service
	MinTrustworthyGroups int // minimum number of build groups to analyze correctness

	// MaxGroups is the maximum number of groups suitable for correctness
	// estimation to fetch.
	// The higher it is, the more statistically significant the results
	// are. If <=0, defaults to DefaultMaxGroups.
	MaxGroups int
	// MaxBuildAge, if >0, is the maximum age of builds to consider.
	MaxBuildAge time.Duration
}

// Analyze compares buildbot and LUCI tryjobs.
// Logs details of inconsistencies.
func (t *Tryjobs) Analyze(c context.Context, builder, buildbotBucket, luciBucket string, currentStatus storage.MigrationStatus) (
	result *storage.BuilderMigration, detailsHTML string, err error) {

	comp, err := t.analyze(c, builder, buildbotBucket, luciBucket, currentStatus)
	if err != nil {
		return nil, "", err
	}

	t.logDiff(c, comp)

	detailsBuf := &bytes.Buffer{}
	if err := tmplDetails.Execute(detailsBuf, comp); err != nil {
		return nil, "", errors.Annotate(err, "could not render report template").Err()
	}
	return &comp.BuilderMigration, detailsBuf.String(), nil
}

func (t *Tryjobs) logDiff(c context.Context, d *diff) {
	timeRange := func(s groupSide) string {
		const layout = "Jan 2 15:04:05.000000000"
		oldest := s[0].CreationTime.Format(layout)
		newest := s[len(s)-1].CreationTime.Format(layout)
		return fmt.Sprintf("[%s..%s]", oldest, newest)
	}

	logGroups := func(category string, groups []*group) {
		logging.Infof(c, "%d %s groups", len(groups), category)
		for _, g := range groups {
			logging.Infof(
				c,
				"  group %q, buildbot %s, LUCI %s",
				g.Key, timeRange(g.Buildbot), timeRange(g.LUCI))
		}
	}

	logGroups("consistent", d.ConsistentGroups)
	logGroups("false failure", d.FalseFailures)
	logGroups("false success", d.FalseSuccesses)
}

func (t *Tryjobs) analyze(c context.Context, builder, buildbotBucket, luciBucket string, currentStatus storage.MigrationStatus) (*diff, error) {
	logging.Infof(c, "analyzing builder %q on %q and %q", builder, buildbotBucket, luciBucket)

	f := fetcher{
		HTTP:           t.HTTP,
		Buildbucket:    t.Buildbucket,
		Builder:        builder,
		BuildbotBucket: buildbotBucket,
		LUCIBucket:     luciBucket,
		MaxGroups:      t.MaxGroups,
	}
	if f.MaxGroups <= 0 {
		f.MaxGroups = DefaultMaxGroups
	}
	if t.MaxBuildAge > 0 {
		f.MinCreationDate = clock.Now(c).Add(-t.MaxBuildAge)
	}
	groups, err := f.Fetch(c)
	if err != nil {
		return nil, err
	}

	comp := compare(groups, t.MinTrustworthyGroups, currentStatus)
	comp.AnalysisTime = clock.Now(c)
	comp.MinBuildAge = comp.AnalysisTime.Sub(f.MinCreationDate)
	return comp, nil
}

type fetcher struct {
	HTTP                       *http.Client
	Buildbucket                *bbapi.Service
	MaxGroups                  int
	Builder                    string
	BuildbotBucket, LUCIBucket string
	MinCreationDate            time.Time
}

// fetchGroup is an intermediate representation of a group.
type fetchGroup struct {
	group
	err chan error
}

// Fetch fetches Buildbot and LUCI builds, groups and joins them by patchset
// until it collects f.MaxGroups of trustworthy groups.
// The builds in groups are ordered from oldest to newest.
func (f *fetcher) Fetch(c context.Context) ([]*group, error) {
	// LUCI builds are scheduled for a fraction of patchsets, so we should avoid
	// fetching Buildbot builds that will be later discarded because there are
	// no corresponding LUCI builds.
	//
	// The algorithm:
	// - start fetching LUCI builds (newest first).
	// - for each new buildset, make a group and fetch corresponding Buildbot
	//   builds
	// - If the group is not trustworthy, discard
	// - stop fetching LUCI builds when maxGroups groups are collected

	const luciBatchSize = 100
	// keys channel controls the lifetime of fetchGroups call (below).
	keys := make(chan groupKey, luciBatchSize)
	// calling cancelKeyFetcher will cause keys channel to close.
	fetchKeysCtx, cancelKeyFetcher := context.WithCancel(c)
	var keysErr error
	go func() {
		defer close(keys)
		keysErr = f.fetchGroupKeys(fetchKeysCtx, keys)
		if keysErr == context.Canceled {
			// This is expected. We should not return this from Fetch.
			keysErr = nil
		}
	}()

	// fetchGroups will return when keys channel is closed.
	// cancelKeyFetcher causes keys channel to close.
	result, err := f.fetchGroups(c, keys, cancelKeyFetcher)
	// All goroutine defined above must exit by this time.
	switch {
	case err != nil:
		return nil, errors.Annotate(err, "could not fetch build groups").Err()
	case keysErr != nil:
		return nil, errors.Annotate(keysErr, "could not fetch build group keys").Err()
	case c.Err() != nil:
		return nil, c.Err()
	}

	return result, nil
}

type properties struct {
	GotRevision string `json:"got_revision"`
}

// fetchGroupKeys fetches group keys of completed LUCI builds
// until c is cancelled.
func (f *fetcher) fetchGroupKeys(c context.Context, keys chan groupKey) error {
	req := f.Buildbucket.Search()
	req.Context(c)
	req.Bucket(f.LUCIBucket)
	req.Status(bbapi.StatusCompleted)
	req.Tag(strpair.Format(buildbucket.TagBuilder, f.Builder))
	req.CreationTsLow(buildbucket.FormatTimestamp(f.MinCreationDate))
	req.IncludeExperimental(true)
	req.Fields("builds(tags, result_details_json)")
	if cap(keys) > 0 {
		req.MaxBuilds(int64(cap(keys)))
	}

	foundBuilds := make(chan *bbapi.ApiCommonBuildMessage, cap(keys))
	var searchErr error
	go func() {
		defer close(foundBuilds)
		searchErr = req.Run(foundBuilds, 0, nil)
	}()

	seen := make(map[groupKey]struct{}, DefaultMaxGroups+groupFetchWorkers)
	for msg := range foundBuilds {
		var b buildbucket.Build
		var props properties
		b.Output.Properties = &props
		if err := b.ParseMessage(msg); err != nil {
			return errors.Annotate(err, "parsing build %d", msg.Id).Err()
		}

		var change *buildbucket.GerritChange
		for _, bs := range b.BuildSets {
			if cl, ok := bs.(*buildbucket.GerritChange); ok {
				if change != nil {
					logging.Warningf(c, "build %d has multiple Gerrit changes; using first one, %q", b.ID, change)
					break
				}
				change = cl
			}
		}
		if change == nil {
			logging.Infof(c, "skipped build %d: no gerrit change", b.ID)
			continue
		}

		key := groupKey{
			GerritChange: *change,
			GotRevision:  props.GotRevision,
		}
		if _, ok := seen[key]; !ok {
			keys <- key
			seen[key] = struct{}{}
		}
	}

	return searchErr
}

// fetchGroups fetches a build group for each group key.
// Each build group has LUCI and Buildbot builds.
// fetchGroups stops as soon as the minimum number of trustworthy groups is
// reached; then it returns all the groups it fetched.
// The order of groups corresponds to the order of buildSets.
// This function is deterministic.
//
// cancel must close keys.
func (f *fetcher) fetchGroups(c context.Context, keys <-chan groupKey, cancel context.CancelFunc) (groups []*group, err error) {
	origC := c
	origCancel := cancel

	// fetching individual groups can take long. Give it 30sec less.
	deadline, ok := c.Deadline()
	if !ok {
		panic("context does not have a deadline")
	}
	c, _ = clock.WithDeadline(c, deadline.Add(-30*time.Second))
	defer func() {
		if errors.Unwrap(err) == context.DeadlineExceeded && origC.Err() != context.DeadlineExceeded {
			err = nil
		}
	}()

	// make `cancel` cancel c too
	c, cancelC := context.WithCancel(c)
	cancel = func() {
		origCancel()
		cancelC()
	}

	groupC := make(chan *fetchGroup, 1)
	go func() {
		// this goroutine is referred to as "master goroutine"

		defer close(groupC)
		// this call returns when keys is closed, which is caused by calling
		// cancel().
		err := parallel.WorkPool(groupFetchWorkers, func(work chan<- func() error) {
			for key := range keys {
				if c.Err() != nil {
					return
				}

				g := &fetchGroup{}
				g.Key = key
				g.err = make(chan error, 1)
				groupC <- g

				// start fetching builds for this group.
				work <- func() error {
					var err error
					defer func() { g.err <- err }()
					if c.Err() == nil {
						err = f.fetchGroup(c, g)
					}
					return nil
				}
			}
		})
		if err != nil {
			panic(err) // we only return nil in work functions
		}
	}()

	var result []*group
	trustworthyGroups := 0

loop:
	for g := range groupC {
		select {
		case <-c.Done():
			// the master goroutine will stop on its own, since it checks c.Err
			return result, c.Err()

		case err = <-g.err:
			if err != nil {
				break loop
			}
			result = append(result, &g.group)
			if g.trustworthy() {
				trustworthyGroups++
				if trustworthyGroups >= f.MaxGroups {
					break loop
				}
			}
		}
	}

	// cancel and drain/wait for the master goroutine
	cancel()
	for range groupC {
	}
	return result, err
}

// fetchGroup fetches buildbot and LUCI builds.
func (f *fetcher) fetchGroup(c context.Context, g *fetchGroup) error {
	var wg sync.WaitGroup
	fetchSide := func(bucket string, side *groupSide, err *error) {
		defer wg.Done()
		req := f.Buildbucket.Search()
		req.Context(c)
		req.Bucket(bucket)
		req.Status(bbapi.StatusCompleted)
		req.Tag(
			strpair.Format(buildbucket.TagBuilder, f.Builder),
			strpair.Format(buildbucket.TagBuildSet, g.Key.GerritChange.String()))
		req.CreationTsLow(buildbucket.FormatTimestamp(f.MinCreationDate))
		req.IncludeExperimental(true)
		req.Fields(
			"builds(cancelation_reason)",
			"builds(completed_ts)",
			"builds(created_ts)",
			"builds(failure_reason)",
			"builds(result)",
			"builds(result_details_json)",
			"builds(started_ts)",
			"builds(status)",
			"builds(url)",
		)
		var msgs []*bbapi.ApiCommonBuildMessage
		msgs, *err = req.Fetch(0, nil)
		if *err != nil {
			return
		}

		builds := make(groupSide, 0, len(msgs))
		for _, msg := range msgs {
			var props properties
			b := &buildbucket.Build{}
			b.Output.Properties = &props

			if *err = b.ParseMessage(msg); *err != nil {
				return
			}

			if props.GotRevision != g.Key.GotRevision {
				// This is very inefficient, but this whole file should be
				// rewritten in SQL anyway.
				continue
			}

			dur, _ := b.RunDuration()
			builds = append(builds, &build{
				Status:         b.Status,
				CreationTime:   b.CreationTime,
				CompletionTime: b.CompletionTime,
				RunDuration:    dur,
				URL:            b.URL,
			})
		}

		// Reverse order to make it oldest-to-newest.
		for i := 0; i < len(builds)/2; i++ {
			j := len(builds) - 1 - i
			builds[i], builds[j] = builds[j], builds[i]
		}

		*side = builds
	}

	wg.Add(2)
	var buildbotErr, luciErr error
	go fetchSide(f.BuildbotBucket, &g.Buildbot, &buildbotErr)
	go fetchSide(f.LUCIBucket, &g.LUCI, &luciErr)
	wg.Wait()

	switch {
	case buildbotErr != nil:
		return errors.Annotate(buildbotErr, "could not fetch buildbot builds of key %q", &g.Key).Err()
	case luciErr != nil:
		return errors.Annotate(luciErr, "could not fetch LUCI builds of key %q", &g.Key).Err()
	default:
		return nil
	}
}
