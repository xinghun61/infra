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
	"go.chromium.org/luci/common/data/stringset"
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

	// mocked in tests
	patchSetAbsent patchSetAbsenceChecker
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
		patchSetAbsent: t.patchSetAbsent,
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

	// mocked in tests
	patchSetAbsent patchSetAbsenceChecker
}

// fetchGroup is an intermediate representation of a group.
type fetchGroup struct {
	sync.Mutex
	group
	err chan error
}

// locked calls f under lock.
func (g *fetchGroup) locked(f func()) {
	g.Lock()
	defer g.Unlock()
	f()
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
	// buildSets channel controls the lifetime of fetchGroups call (below).
	buildSets := make(chan buildbucket.BuildSet, luciBatchSize)
	// calling cancelBSFetcher will cause buildSets to close.
	fetchBSCtx, cancelBSFetcher := context.WithCancel(c)
	var bsErr error
	go func() {
		defer close(buildSets)
		bsErr = f.fetchBuildSets(fetchBSCtx, buildSets)
		if bsErr == context.Canceled {
			// This is expected. We should not return this from Fetch.
			bsErr = nil
		}
	}()

	// fetchGroups will return when buildSets channel is closed.
	// cancelBSFetcher causes buildSets channel to close.
	result, err := f.fetchGroups(c, buildSets, cancelBSFetcher)
	// All goroutine defined above must exit by this time.
	switch {
	case err != nil:
		return nil, err
	case bsErr != nil:
		return nil, bsErr
	case c.Err() != nil:
		return nil, c.Err()
	}

	return result, nil
}

// fetchBuildSets fetches buildsets of completed LUCI builds until c is
// cancelled.
// Ignores builds for non-existing patchsets.
func (f *fetcher) fetchBuildSets(c context.Context, buildSets chan buildbucket.BuildSet) error {
	req := f.Buildbucket.Search()
	req.Context(c)
	req.Bucket(f.LUCIBucket)
	req.Status(bbapi.StatusCompleted)
	req.Tag(strpair.Format(buildbucket.TagBuilder, f.Builder))
	req.CreationTsLow(buildbucket.FormatTimestamp(f.MinCreationDate))
	req.Fields("builds(tags)") // we need only buildset tag
	if cap(buildSets) > 0 {
		req.MaxBuilds(int64(cap(buildSets)))
	}

	foundBuilds := make(chan *bbapi.ApiCommonBuildMessage, cap(buildSets))
	var searchErr error
	go func() {
		defer close(foundBuilds)
		searchErr = req.Run(foundBuilds, 0, nil)
	}()

	// check that Rietveld patchsets still exist.
	psAbsent := f.patchSetAbsent
	if psAbsent == nil {
		psAbsent = patchSetAbsent // real one
	}

	seen := stringset.New(DefaultMaxGroups + groupFetchWorkers)
	for msg := range foundBuilds {
		var b buildbucket.Build
		if err := b.ParseMessage(msg); err != nil {
			return errors.Annotate(err, "parsing build %d", msg.Id).Err()
		}

		switch {
		case len(b.BuildSets) == 0:
			logging.Infof(c, "skipped build %d: no buildset tag", b.ID)
			continue
		case len(b.BuildSets) > 1:
			logging.Warningf(c, "build %d has multiple buildsets; using first one, %q", b.ID, b.BuildSets[0])
		}
		bs := b.BuildSets[0]

		if !seen.Add(bs.String()) {
			continue
		}

		// Serialize all requests to Rietveld b/c
		// 1) This code is much simpler this way
		// 2) We don't want to hammer Rietveld too much
		// 3) The channel of buildSets is buffered, so underlying fetching
		//    of LUCI builds and following fetching of Buildbot builds
		//    won't be entirely blocked.
		absent, err := psAbsent(c, f.HTTP, bs)
		if err != nil {
			return err
		}
		if absent {
			logging.Debugf(c, "skipped build %d: patchset %s does not exist", b.ID, bs)
			continue
		}
		buildSets <- bs
	}

	return searchErr
}

// fetchGroups fetches a build group for each buildset.
// Each build group has LUCI and Buildbot builds.
// fetchGroups stops as soon as the minimum number of trustworthy groups is
// reached; then it returns all the groups it fetched.
// The order of groups corresponds to the order of buildSets.
// This function is deterministic.
//
// cancel must close luciBuilds.
func (f *fetcher) fetchGroups(c context.Context, buildSets <-chan buildbucket.BuildSet, cancel context.CancelFunc) ([]*group, error) {
	// make `cancel` cancel c too
	origCancel := cancel
	c, cancelC := context.WithCancel(c)
	cancel = func() {
		origCancel()
		cancelC()
	}

	groupC := make(chan *fetchGroup, 1)
	go func() {
		// this goroutine is referred to as "master goroutine"

		defer close(groupC)
		// this call returns when buildSets is closed, which is caused by calling
		// cancel().
		err := parallel.WorkPool(groupFetchWorkers, func(work chan<- func() error) {
			for bs := range buildSets {
				if c.Err() != nil {
					return
				}

				g := &fetchGroup{}
				g.err = make(chan error, 1)
				g.Key = bs.String()
				type withURL interface {
					URL() string
				}
				if urlable, ok := bs.(withURL); ok {
					g.KeyURL = urlable.URL()
				}
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
	var err error
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
			strpair.Format(buildbucket.TagBuildSet, g.Key))
		req.CreationTsLow(buildbucket.FormatTimestamp(f.MinCreationDate))
		req.Fields("builds(status, result, failure_reason, cancelation_reason, created_ts, started_ts, completed_ts, url)")
		var msgs []*bbapi.ApiCommonBuildMessage
		msgs, *err = req.Fetch(0, nil)
		if *err != nil {
			return
		}

		builds := make(groupSide, len(msgs))
		for i, msg := range msgs {
			// Reverse order to make it oldest-to-newest.
			b := &buildbucket.Build{}
			if *err = b.ParseMessage(msg); *err != nil {
				return
			}
			dur, _ := b.RunDuration()
			builds[len(msgs)-1-i] = &build{
				Status:         b.Status,
				CreationTime:   b.CreationTime,
				CompletionTime: b.CompletionTime,
				RunDuration:    dur,
				URL:            b.URL,
			}
		}
		*side = builds
	}

	wg.Add(2)
	var buildbotErr, luciErr error
	go fetchSide(f.BuildbotBucket, &g.Buildbot, &buildbotErr)
	go fetchSide(f.LUCIBucket, &g.LUCI, &luciErr)
	wg.Wait()
	if buildbotErr != nil {
		return buildbotErr
	}
	return luciErr
}
