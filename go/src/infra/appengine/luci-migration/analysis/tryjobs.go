// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

// Package analysis compares buildbucket builds on LUCI and Buildbot.
package analysis

import (
	"bytes"
	"net/http"
	"sync"
	"sync/atomic"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/api/buildbucket/buildbucket/v1"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/sync/parallel"

	"infra/appengine/luci-migration/bbutil"
	"infra/appengine/luci-migration/bbutil/buildset"
	"infra/appengine/luci-migration/storage"
)

// DefaultMaxGroups is the default number of build groups to fetch.
const DefaultMaxGroups = 100

// BucketBuilder is a combination of a build bucket and a builder name.
type BucketBuilder struct {
	Bucket  string
	Builder string
}

// String implements fmt.Stringer.
func (b BucketBuilder) String() string {
	return b.Bucket + ":" + b.Builder
}

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
func (t *Tryjobs) Analyze(c context.Context, buildbotBuilder, luciBuilder BucketBuilder) (
	result *storage.BuilderMigration, detailsHTML string, err error) {

	comp, err := t.analyze(c, buildbotBuilder, luciBuilder)
	if err != nil {
		return nil, "", err
	}

	detailsBuf := &bytes.Buffer{}
	if err := tmplDetails.Execute(detailsBuf, comp); err != nil {
		return nil, "", errors.Annotate(err, "could not render report template").Err()
	}
	return &comp.BuilderMigration, detailsBuf.String(), nil
}

func (t *Tryjobs) analyze(c context.Context, buildbotBuilder, luciBuilder BucketBuilder) (*diff, error) {
	logging.Infof(c, "comparing %q to %q", luciBuilder, buildbotBuilder)

	f := fetcher{
		HTTP:           t.HTTP,
		Buildbucket:    t.Buildbucket,
		LUCI:           luciBuilder,
		Buildbot:       buildbotBuilder,
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

	comp := compare(groups, t.MinTrustworthyGroups)
	comp.AnalysisTime = clock.Now(c)
	comp.MinBuildAge = comp.AnalysisTime.Sub(f.MinCreationDate)
	return comp, nil
}

type fetcher struct {
	HTTP            *http.Client
	Buildbucket     *buildbucket.Service
	MaxGroups       int
	Buildbot, LUCI  BucketBuilder
	MinCreationDate time.Time

	// mocked in tests
	patchSetAbsent patchSetAbsenceChecker
}

// fetchGroup is an intermediate representation of a group.
type fetchGroup struct {
	sync.Mutex
	group
	accepted bool // true if this group is counted as trustworthy
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
	// luciBuilds channel controls the lifetime of joinBuilds call (below).
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

	// joinBuilds will return when luciBuilds channel is closed.
	// cancelLUCIFetcher causes luciBuilds channel to close.
	result, err := f.joinBuilds(c, luciBuilds, cancelLUCIFetcher)
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
	req.Bucket(f.LUCI.Bucket)
	req.Status(bbutil.StatusCompleted)
	req.Tag(bbutil.FormatTag("builder", f.LUCI.Builder))
	if cap(builds) > 0 {
		req.MaxBuilds(int64(cap(builds)))
	}

	foundBuilds := make(buildChan, cap(builds))
	var searchErr error
	go func() {
		defer close(foundBuilds)
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

// joinBuilds listens to luciBuilds channel and for each buildset fetches
// Buildbot builds. It returns all build groups it finds as soon as minimum
// number of trustworthy groups is reached.
func (f *fetcher) joinBuilds(c context.Context, luciBuilds buildChan, stop func()) ([]*group, error) {
	var trustworthyGroups int32
	considerStopping := func(i *fetchGroup) {
		if !i.accepted && i.trustworthy() {
			i.accepted = true
			if atomic.AddInt32(&trustworthyGroups, 1) >= int32(f.MaxGroups) {
				stop()
			}
		}
	}

	var result []*group
	groups := map[string]*fetchGroup{} // both map and group key is buildset

	// this loop stops when luciBuilds is closed, which is caused by calling
	// stop().
	err := parallel.WorkPool(10, func(work chan<- func() error) {
		for b := range luciBuilds {
			buildSet := bbutil.BuildSet(b)
			if buildSet == "" {
				logging.Debugf(c, "skipped build %d: no buildset tag", b.Id)
				continue
			}

			g := groups[buildSet]
			if g == nil {
				g = &fetchGroup{}
				g.Key = buildSet
				g.KeyURL = buildset.Parse(buildSet).URL()
				groups[buildSet] = g
				result = append(result, &g.group)

				// start fetching Buildbot builds for the same buildset.
				work <- func() error {
					if c.Err() != nil {
						return c.Err() // exit early
					}

					req := f.Buildbucket.Search()
					req.Bucket(f.Buildbot.Bucket)
					req.Status(bbutil.StatusCompleted)
					req.Tag(
						bbutil.FormatTag("builder", f.Buildbot.Builder),
						bbutil.FormatTag(bbutil.TagBuildSet, buildSet))
					builds, err := bbutil.SearchAll(c, req, f.MinCreationDate)
					if err != nil {
						// cancel LUCI build fetcher, which will close
						// luciBuilds channel, which will stop the work
						// generator.
						stop()
						return err
					}

					g.locked(func() {
						g.Buildbot = builds
						g.Buildbot.reverse()
						considerStopping(g)
					})
					return nil
				}
			}

			g.locked(func() {
				// temporarily add in the reverse order
				g.LUCI = append(g.LUCI, b)
				considerStopping(g)
			})
		}
	})
	for _, g := range result {
		g.LUCI.reverse()
	}
	return result, err
}
