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
	"net/http"
	"sync"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"

	"infra/appengine/luci-migration/bbutil"
	"infra/appengine/luci-migration/bbutil/buildset"
	"infra/appengine/luci-migration/storage"
)

// DefaultMaxGroups is the default number of build groups to fetch.
const DefaultMaxGroups = 100

// Tryjobs compares LUCI and Buildbot tryjobs.
type Tryjobs struct {
	HTTP                 *http.Client
	Buildbucket          *buildbucket.Service
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
func (t *Tryjobs) Analyze(c context.Context, builder, buildbotBucket, luciBucket string, currentStatus storage.MigrationStatus) (
	result *storage.BuilderMigration, detailsHTML string, err error) {

	comp, err := t.analyze(c, builder, buildbotBucket, luciBucket, currentStatus)
	if err != nil {
		return nil, "", err
	}

	detailsBuf := &bytes.Buffer{}
	if err := tmplDetails.Execute(detailsBuf, comp); err != nil {
		return nil, "", errors.Annotate(err, "could not render report template").Err()
	}
	return &comp.BuilderMigration, detailsBuf.String(), nil
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
	Buildbucket                *buildbucket.Service
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

type buildChan chan *buildbucket.ApiCommonBuildMessage

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
	// luciBuilds channel controls the lifetime of fetchGroups call (below).
	luciBuilds := make(buildChan, luciBatchSize)
	// calling cancelLUCIFetcher will cause luciBuilds to close.
	luciFetchCtx, cancelLUCIFetcher := context.WithCancel(c)
	var luciFetchErr error
	go func() {
		defer close(luciBuilds)
		luciFetchErr = f.fetchLUCIBuilds(luciFetchCtx, luciBuilds)
		if luciFetchErr == context.Canceled {
			// This is expected. We should not return this from Fetch.
			luciFetchErr = nil
		}
	}()

	// fetchGroups will return when luciBuilds channel is closed.
	// cancelLUCIFetcher causes luciBuilds channel to close.
	result, err := f.fetchGroups(c, luciBuilds, cancelLUCIFetcher)
	// All goroutine defined above must exit by this time.
	switch {
	case err != nil:
		return nil, err
	case luciFetchErr != nil:
		return nil, luciFetchErr
	case c.Err() != nil:
		return nil, c.Err()
	}

	return result, nil
}

// fetchLUCIBuilds fetches completed LUCI builds until c is cancelled.
// Ignores builds for non-existing patchsets.
func (f *fetcher) fetchLUCIBuilds(c context.Context, builds buildChan) error {
	req := f.Buildbucket.Search()
	req.Bucket(f.LUCIBucket)
	req.Status(bbutil.StatusCompleted)
	req.Tag(bbutil.FormatTag("builder", f.Builder))
	if cap(builds) > 0 {
		req.MaxBuilds(int64(cap(builds)))
	}

	foundBuilds := make(buildChan, cap(builds))
	var searchErr error
	go func() {
		defer close(foundBuilds)
		searchErr = bbutil.Search(c, req, f.MinCreationDate, foundBuilds)
		if searchErr != nil {
			return
		}

		// TODO(nodir): remove a week after no build has "LUCI " builder name prefix.
		req.Tag(bbutil.FormatTag("builder", "LUCI "+f.Builder)) // overrides previous req.Tag() call
		searchErr = bbutil.Search(c, req, f.MinCreationDate, foundBuilds)
	}()

	// check that Rietveld patchsets still exist.
	psAbsent := f.patchSetAbsent
	if psAbsent == nil {
		psAbsent = patchSetAbsent // real one
	}
	absentCache := make(map[string]bool, f.MaxGroups*2)
	for b := range foundBuilds {
		bs := bbutil.BuildSet(b)
		absent, ok := absentCache[bs]
		if !ok {
			// Serialize all requests to Rietveld b/c
			// 1) This code is much simpler this way
			// 2) We don't want to hammer Rietveld too much
			// 3) The channel of builds is buffered, so underlying fetching
			//    of LUCI builds and following fetching of Buildbot builds
			//    won't be entirely blocked.
			var err error
			absent, err = psAbsent(c, f.HTTP, buildset.Parse(bs))
			if err != nil {
				return err
			}
			absentCache[bs] = absent
		}
		if absent {
			logging.Debugf(c, "skipped build %d: patchset %s does not exist", b.Id, bs)
		} else {
			builds <- b
		}
	}

	return searchErr
}

// fetchGroups listens to luciBuilds channel and for each new buildset it
// fetches a build group. Each build group has LUCI and Buildbot builds.
// fetchGroups stops as soon as the minimum number of trustworthy groups is
// reached; then it returns all the groups it fetched.
// The order of groups corresponds to the order of luciBuilds.
// This function is deterministic.
//
// cancel must close luciBuilds.
func (f *fetcher) fetchGroups(c context.Context, luciBuilds buildChan, cancel context.CancelFunc) ([]*group, error) {
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
		// this call returns when luciBuilds is closed, which is caused by calling
		// cancel().
		err := parallel.WorkPool(10, func(work chan<- func() error) {
			seen := map[string]*fetchGroup{} // both map and group key is buildset
			for b := range luciBuilds {
				if c.Err() != nil {
					return
				}
				buildSet := bbutil.BuildSet(b)
				if buildSet == "" {
					logging.Debugf(c, "skipped build %d: no buildset tag", b.Id)
					continue
				}

				if _, alreadyProcessing := seen[buildSet]; alreadyProcessing {
					continue
				}

				g := &fetchGroup{}
				g.err = make(chan error, 1)
				g.Key = buildSet
				g.KeyURL = buildset.Parse(buildSet).URL()
				seen[buildSet] = g
				groupC <- g

				// start fetching builds for this group.
				work <- func() error {
					var err error
					defer func() { g.err <- err }()
					if c.Err() == nil {
						err = f.fetchGroup(c, g) // writes error to g.err
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
				if trustworthyGroups > f.MaxGroups {
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
		req.Bucket(bucket)
		req.Status(bbutil.StatusCompleted)
		req.Tag(
			bbutil.FormatTag("builder", f.Builder),
			bbutil.FormatTag(bbutil.TagBuildSet, g.Key))
		var builds []*buildbucket.ApiCommonBuildMessage
		builds, *err = bbutil.SearchAll(c, req, f.MinCreationDate)
		if *err != nil {
			return
		}

		// TODO(nodir): remove a week after no build has "LUCI " builder name prefix.
		req.Tag(
			bbutil.FormatTag("builder", "LUCI "+f.Builder),
			bbutil.FormatTag(bbutil.TagBuildSet, g.Key)) // overrides previous req.Tag() call
		var prefixedBuilds []*buildbucket.ApiCommonBuildMessage
		prefixedBuilds, *err = bbutil.SearchAll(c, req, f.MinCreationDate)
		if *err != nil {
			return
		}
		// this preserves order because prefixed builds are older than
		// non-prefixed on a given builder (because we don't go back to
		// prefixed).
		builds = append(builds, prefixedBuilds...)

		// Reverse order to make it oldest-to-newest.
		for i := 0; i < len(builds)/2; i++ {
			builds[i], builds[len(builds)-1-i] = builds[len(builds)-1-i], builds[i]
		}
		*side = groupSide(builds)
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
