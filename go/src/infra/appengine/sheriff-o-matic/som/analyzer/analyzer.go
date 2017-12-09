// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyzer

import (
	"errors"
	"expvar"
	"fmt"
	"net/url"
	"sort"
	"strings"
	"sync"
	"time"

	"golang.org/x/net/context"

	"infra/appengine/sheriff-o-matic/som/analyzer/regrange"
	"infra/appengine/sheriff-o-matic/som/analyzer/step"
	"infra/appengine/sheriff-o-matic/som/client"
	"infra/monitoring/messages"

	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
)

const (
	// StepCompletedRun is a synthetic step name used to indicate the build run is complete.
	StepCompletedRun = "completed run"

	// Step result values.
	resInfraFailure = float64(4)

	// This is pretty aggressive, and tuned mainly for chromium.perf. Consider
	// making this a per-tree setting.
	maxConcurrentBuilders = 2

	// This is a guess, and should be tuned
	maxConcurrentBuilds = 4
)

var (
	expvars = expvar.NewMap("analyzer")

	// Link hosts which are allowed to be uploaded to SOM. Whitelist for security.
	allowedLinkHosts = []string{
		"chromeperf.appspot.com",        // Perf dashboard links
		"bugs.chromium.org",             // Monorail, just in case
		"crbug.com",                     // Monorail as well
		"console.developers.google.com", // Cloud storage links
		"chromium-swarm.appspot.com",    // Swarming results
		"isolateserver.appspot.com",     // Isolate server
		"storage.cloud.google.com",      // Android tests
	}
)

var (
	errNoBuildSteps      = errors.New("No build steps")
	errNoRecentBuilds    = errors.New("No recent builds")
	errNoCompletedBuilds = errors.New("No completed builds")
)

// Analyzer runs the process of checking masters, builders, test results and so on,
// in order to produce alerts.
type Analyzer struct {
	// MaxRecentBuilds is the maximum number of recent builds to check, per builder.
	MaxRecentBuilds int

	// MinRecentBuilds is the minimum number of recent builds to check, per builder.
	MinRecentBuilds int

	// HungBuilerThresh is the maxumum length of time a builder may be in state "building"
	// before triggering a "hung builder" alert.
	HungBuilderThresh time.Duration

	// OfflineBuilderThresh is the maximum length of time a builder may be in state "offline"
	//  before triggering an "offline builder" alert.
	OfflineBuilderThresh time.Duration

	// IdleBuilderCountThresh is the maximum number of builds a builder may have in queue
	// while in the "idle" state before triggering an "idle builder" alert.
	IdleBuilderCountThresh int64

	// StaleMasterThreshold is the maximum age that master data from CBE can be before
	// triggering a "stale master" alert.
	StaleMasterThreshold time.Duration

	// Gatekeeper is a the parsed gatekeeper.json config file.
	Gatekeeper *GatekeeperRules

	// These limit the scope analysis, useful for debugging.
	MasterOnly  string
	BuilderOnly string
	BuildOnly   int64

	// rslck protects revisionSummaries from concurrent access.
	rslck             *sync.Mutex
	revisionSummaries map[string]messages.RevisionSummary

	reasonFinder   step.ReasonFinder
	regrangeFinder regrange.Finder

	// Now is useful for mocking the system clock in testing and simulating time
	// during replay.
	Now func() time.Time
}

// New returns a new Analyzer. If client is nil, it assigns a default implementation.
// maxBuilds is the maximum number of builds to check, per builder.
func New(minBuilds, maxBuilds int) *Analyzer {
	return &Analyzer{
		MaxRecentBuilds:        maxBuilds,
		MinRecentBuilds:        minBuilds,
		HungBuilderThresh:      3 * time.Hour,
		OfflineBuilderThresh:   90 * time.Minute,
		IdleBuilderCountThresh: 50,
		StaleMasterThreshold:   10 * time.Minute,
		Gatekeeper:             &GatekeeperRules{},
		rslck:                  &sync.Mutex{},
		revisionSummaries:      map[string]messages.RevisionSummary{},
		reasonFinder:           step.ReasonsForFailures,
		regrangeFinder:         regrange.Default,
		Now: func() time.Time {
			return time.Now()
		},
	}
}

// MasterAlerts returns alerts generated from the master.
func (a *Analyzer) MasterAlerts(ctx context.Context, master *messages.MasterLocation, be *messages.BuildExtract) []messages.Alert {
	ret := []messages.Alert{}

	// Copied logic from builder_messages.
	// No created_timestamp should be a warning sign, no?
	if be.CreatedTimestamp == messages.EpochTime(0) {
		return ret
	}
	expvars.Add("MasterAlerts", 1)
	defer expvars.Add("MasterAlerts", -1)

	elapsed := a.Now().Sub(be.CreatedTimestamp.Time())
	if elapsed > a.StaleMasterThreshold {
		ret = append(ret, messages.Alert{
			Key:       fmt.Sprintf("stale master: %v", master),
			Title:     fmt.Sprintf("Stale %s master data", master),
			Body:      fmt.Sprintf("%dh %2dm elapsed since last update.", int(elapsed.Hours()), int(elapsed.Minutes())),
			StartTime: messages.TimeToEpochTime(be.CreatedTimestamp.Time()),
			Severity:  messages.StaleMaster,
			Time:      messages.TimeToEpochTime(a.Now()),
			Links:     []messages.Link{{Title: "Master", Href: master.URL.String()}},
			Type:      messages.AlertStaleMaster,
			// No extension for now.
		})
	}
	if elapsed < 0 {
		// Add this to the alerts returned, rather than just log it?
		logging.Errorf(ctx, "Master %s timestamp is newer than current time (%s): %s old.", master, a.Now(), elapsed)
	}

	return ret
}

// BuilderAlerts returns alerts generated from builders connected to the master.
func (a *Analyzer) BuilderAlerts(ctx context.Context, tree string, master *messages.MasterLocation, be *messages.BuildExtract) []messages.Alert {

	// TODO: Collect activeBuilds from be.Slaves.RunningBuilds
	type r struct {
		builderName string
		b           messages.Builder
		alerts      []messages.Alert
		err         []error
	}
	c := make(chan r, len(be.Builders))

	workers := len(be.Builders)
	if workers > maxConcurrentBuilders {
		workers = maxConcurrentBuilders
	}

	err := parallel.WorkPool(workers, func(workC chan<- func() error) {
		for builderName, builder := range be.Builders {
			builderName, builder := builderName, builder
			workC <- func() error {
				if a.BuilderOnly != "" && builderName != a.BuilderOnly {
					return nil
				}

				out := r{builderName: builderName, b: builder}
				out.alerts, out.err = a.builderAlerts(ctx, tree, master, builderName, &builder)

				c <- out
				return nil
			}
		}
	})

	if err != nil {
		// Eh... What to do here? Return? But we never return an error from a worker,
		// so I suppose it's not an issue.
		logging.Errorf(ctx, "Error from worker pool: %v", err)
	}

	ret := []messages.Alert{}
	for builderName := range be.Builders {
		if a.BuilderOnly != "" && builderName != a.BuilderOnly {
			continue
		}

		r := <-c
		if len(r.err) != 0 {
			// TODO: add a special alert for this too?
			logging.Errorf(ctx, "Error getting alerts for builder %s: %v", r.builderName, r.err)
		} else {
			ret = append(ret, r.alerts...)
		}
	}

	return ret
}

// TODO: actually write the on-disk cache.
func filenameForCacheKey(cc string) string {
	cc = strings.Replace(cc, "/", "_", -1)
	return fmt.Sprintf("/tmp/dispatcher.cache/%s", cc)
}

func alertKey(master, builder, step, testName string) string {
	return fmt.Sprintf("%s.%s.%s.%s", master, builder, step, testName)
}

// This type is used for sorting build IDs.
type buildNums []int64

func (a buildNums) Len() int           { return len(a) }
func (a buildNums) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }
func (a buildNums) Less(i, j int) bool { return a[i] > a[j] }

// latestBuildStep returns the latest build step name and update time, and an error
// if there were any errors.
func (a *Analyzer) latestBuildStep(b *messages.Build) (lastStep string, lastUpdate messages.EpochTime, err error) {
	if len(b.Steps) == 0 {
		return "", messages.TimeToEpochTime(a.Now()), errNoBuildSteps
	}
	if len(b.Times) > 1 && b.Times[1] != 0 {
		return StepCompletedRun, b.Times[1], nil
	}

	for _, step := range b.Steps {
		if len(step.Times) > 1 && step.Times[1] > lastUpdate {
			// Step is done.
			lastUpdate = step.Times[1]
			lastStep = step.Name
		} else if len(step.Times) > 0 && step.Times[0] > lastUpdate {
			// Step has started.
			lastUpdate = step.Times[0]
			lastStep = step.Name
		}
	}
	return
}

// lastBuild returns the last build (which may or may not have completed) and the last completed build (which may be
// the same as the last build), and any error that occurred while finding them.
func (a *Analyzer) lastBuilds(ctx context.Context, master *messages.MasterLocation, builderName string, recentBuildIDs []int64) (lastBuild, lastCompletedBuild *messages.Build, err error) {
	// Check for stale/idle/offline builders.  Latest build is the first in the list.

	for i, buildNum := range recentBuildIDs {
		logging.Infof(ctx, "Checking last %s/%s build ID: %d", master.Name(), builderName, buildNum)

		var build *messages.Build
		build, err = client.Build(ctx, master, builderName, buildNum)
		if err != nil {
			return
		}

		if i == 0 {
			lastBuild = build
		}

		lastStep, _, _ := a.latestBuildStep(build)
		if lastStep == StepCompletedRun {
			lastCompletedBuild = build
			return
		}
	}

	return nil, nil, errNoCompletedBuilds
}

// TODO: also check the build slaves to see if there are alerts for currently running builds that
// haven't shown up in CBE yet.
func (a *Analyzer) builderAlerts(ctx context.Context, tree string, master *messages.MasterLocation, builderName string, b *messages.Builder) ([]messages.Alert, []error) {
	if len(b.CachedBuilds) == 0 {
		// TODO: Make an alert for this?
		return nil, []error{errNoRecentBuilds}
	}

	recentBuildIDs := b.CachedBuilds
	// Should be a *reverse* sort.
	sort.Sort(buildNums(recentBuildIDs))
	if len(recentBuildIDs) > a.MaxRecentBuilds {
		recentBuildIDs = recentBuildIDs[:a.MaxRecentBuilds]
	}

	alerts, errs := []messages.Alert{}, []error{}

	lastBuild, lastCompletedBuild, err := a.lastBuilds(ctx, master, builderName, recentBuildIDs)
	if err != nil {
		errs = append(errs, err)
		return nil, errs
	}

	if a.Gatekeeper.ExcludeBuilder(ctx, tree, master, builderName) {
		return nil, nil
	}

	// Examining only the latest build is probably suboptimal since if it's still in progress it might
	// not have hit a step that is going to fail and has failed repeatedly for the last few builds.
	// AKA "Reliable failures".  TODO: Identify "Reliable failures"
	lastStep, lastUpdated, err := a.latestBuildStep(lastBuild)
	if err != nil {
		errs = append(errs, fmt.Errorf("Couldn't get latest build step for %s.%s: %v", master.Name(), builderName, err))
		return alerts, errs
	}
	elapsed := a.Now().Sub(lastUpdated.Time())
	links := []messages.Link{
		{Title: "Builder", Href: client.BuilderURL(master, builderName).String()},
		{Title: "Last build", Href: client.BuildURL(master, builderName, lastBuild.Number).String()},
		{Title: "Last build step", Href: client.StepURL(master, builderName, lastStep, lastBuild.Number).String()},
	}

	switch b.State {
	case messages.StateBuilding:
		if elapsed > a.HungBuilderThresh && lastStep != StepCompletedRun {
			alerts = append(alerts, messages.Alert{
				Key:       fmt.Sprintf("%s.%s.hung", master.Name(), builderName),
				Title:     fmt.Sprintf("%s.%s is hung in step %s.", master.Name(), builderName, lastStep),
				Severity:  messages.HungBuilder,
				Time:      messages.TimeToEpochTime(a.Now()),
				StartTime: messages.TimeToEpochTime(lastUpdated.Time()),
				Links:     links,
				Type:      messages.AlertHungBuilder,
			})
			// Note, just because it's building doesn't mean it's in a good state. If the last N builds
			// all failed (for some large N) then this might still be alertable.
		}
	case messages.StateOffline:
		if elapsed > a.OfflineBuilderThresh {
			alerts = append(alerts, messages.Alert{
				Key:       fmt.Sprintf("%s.%s.offline", master.Name(), builderName),
				Title:     fmt.Sprintf("%s.%s is offline.", master.Name(), builderName),
				Severity:  messages.OfflineBuilder,
				Time:      messages.TimeToEpochTime(a.Now()),
				StartTime: messages.TimeToEpochTime(lastUpdated.Time()),
				Links:     links,
				Type:      messages.AlertOfflineBuilder,
			})
		}
	case messages.StateIdle:
		// FIXME: We should also look at amount of time idle, not just number of builds that the builder has idle.
		if b.PendingBuilds > a.IdleBuilderCountThresh {
			alerts = append(alerts, messages.Alert{
				Key:       fmt.Sprintf("%s.%s.idle", master.Name(), builderName),
				Title:     fmt.Sprintf("%s.%s is idle with %d pending builds.", master.Name(), builderName, b.PendingBuilds),
				Severity:  messages.IdleBuilder,
				Time:      messages.TimeToEpochTime(a.Now()),
				StartTime: messages.TimeToEpochTime(lastUpdated.Time()),
				Links:     links,
				Type:      messages.AlertIdleBuilder,
			})
		}
	default:
		logging.Errorf(ctx, "Unknown %s.%s builder state: %s", master.Name(), builderName, b.State)
	}

	// Check for alerts on the most recent complete build
	logging.Infof(ctx, "Checking %d most recent builds for alertable step failures: %s/%s", len(recentBuildIDs), master.Name(), builderName)

	mostRecentComplete := 0
	for i, id := range recentBuildIDs {
		if id == lastCompletedBuild.Number {
			mostRecentComplete = i
		}
	}
	as, es := a.builderStepAlerts(ctx, tree, master, builderName, recentBuildIDs[mostRecentComplete:])
	alerts = append(alerts, as...)
	errs = append(errs, es...)

	return alerts, errs
}

// GetRevisionSummaries returns a slice of RevisionSummaries for the list of hashes.
func (a *Analyzer) GetRevisionSummaries(hashes []string) ([]messages.RevisionSummary, error) {
	ret := []messages.RevisionSummary{}
	for _, h := range hashes {
		a.rslck.Lock()
		s, ok := a.revisionSummaries[h]
		a.rslck.Unlock()
		if !ok {
			return nil, fmt.Errorf("Unrecognized hash:  %s", h)
		}
		ret = append(ret, s)
	}

	return ret, nil
}

// builderStepAlerts scans the steps of recent builds done on a particular builder,
// generating an Alert for each step output that warrants one.  Alerts are then
// merged by key so that failures that occur across a range of builds produce a single
// alert instead of one for each build.
//
// We assume the first build in the list of recent build IDs is the most recent;
// this build is used to select the steps which we think are still failing and
// should show up as alerts.
func (a *Analyzer) builderStepAlerts(ctx context.Context, tree string, master *messages.MasterLocation, builderName string, recentBuildIDs []int64) (alerts []messages.Alert, errs []error) {
	if len(recentBuildIDs) == 0 {
		return nil, nil
	}

	sort.Sort(buildNums(recentBuildIDs))
	// Check for alertable step failures.  We group them by key to de-duplicate and merge values
	// once we've scanned everything.
	stepAlertsByKey := map[string][]*messages.Alert{}

	importantFailures, err := a.findImportantFailures(ctx, master, builderName, recentBuildIDs)
	if err != nil {
		return nil, []error{err}
	}

	importantAlerts, err := a.stepFailureAlerts(ctx, tree, importantFailures, []*messages.FinditResult{})
	if err != nil {
		return nil, []error{err}
	}

	importantKeys := stringset.New(0)
	for _, alr := range importantAlerts {
		importantKeys.Add(alr.Key)
	}
	if err != nil {
		return nil, []error{err}
	}
	if len(importantFailures) == 0 {
		return nil, errs
	}

	// Get findit results for latestBuild.
	stepNames := make([]string, len(importantFailures))
	for i, f := range importantFailures {
		stepNames[i] = f.Step.Name
	}
	latestBuild := recentBuildIDs[0]

	// NOTE: we only use the most recent build ID now, because currently the only
	// time we would need to check multiple builds is for official builds, which
	// right now are internal and not supported by findit.
	finditResults := []*messages.FinditResult{}
	if tree == "chromium" {
		finditResults, err = client.Findit(ctx, master, builderName, latestBuild, stepNames)
		if err != nil {
			logging.Errorf(ctx, "while getting findit results for build: %s", err)
		}
	}

	type r struct {
		alrs     []messages.Alert
		buildNum int64
	}
	alertsPerBuild := make([][]messages.Alert, len(recentBuildIDs))
	goodBuilds := make([]int64, len(recentBuildIDs))

	workers := len(recentBuildIDs)
	if workers > maxConcurrentBuilds {
		workers = maxConcurrentBuilds
	}

	err = parallel.WorkPool(workers, func(workC chan<- func() error) {
		for i, buildNum := range recentBuildIDs {
			buildNum := buildNum
			i := i
			// Initialize to -1, since 0 is a valid build number
			goodBuilds[i] = -1
			workC <- func() error {
				failures, err := a.stepFailures(ctx, master, builderName, buildNum)
				if err != nil {
					return err
				}

				if len(failures) == 0 {
					// Bail as soon as we find a successful build.
					goodBuilds[i] = buildNum
					return nil
				}

				fResults := []*messages.FinditResult{}
				if buildNum == latestBuild {
					fResults = finditResults
				} else {
					// Get findit results for other build.
					stepNames := make([]string, len(failures))
					for i, f := range failures {
						stepNames[i] = f.Step.Name
					}

					if tree == "chromium" {
						f, err := client.Findit(ctx, master, builderName, buildNum, stepNames)
						if err != nil {
							logging.Errorf(ctx, "while getting findit results for build: %s", err)
						} else {
							fResults = f
						}
					}
				}

				as, err := a.stepFailureAlerts(ctx, tree, failures, fResults)
				if err != nil {
					return err
				}
				alertsPerBuild[i] = as
				return nil
			}
		}
	})

	if err != nil {
		errs = append(errs, err)
	}

	firstSuccessfulBuild := int64(-1)
	for _, num := range goodBuilds {
		if firstSuccessfulBuild == -1 || num > firstSuccessfulBuild {
			firstSuccessfulBuild = num
		}
	}

	for i, alrs := range alertsPerBuild {
		buildNum := recentBuildIDs[i]
		if buildNum <= firstSuccessfulBuild && firstSuccessfulBuild != -1 {
			continue
		}

		// Group alerts by key so they can be merged across builds/regression ranges.
		for _, alr := range alrs {
			// Needed because we append the reference below
			alr := alr
			if importantKeys.Has(alr.Key) {
				stepAlertsByKey[alr.Key] = append(stepAlertsByKey[alr.Key], &alr)
			}
		}
	}

	// Now coalesce alerts with the same key into single alerts with merged properties.
	for key, keyedAlerts := range stepAlertsByKey {
		mergedAlert := keyedAlerts[0] // Merge everything into the first one
		mergedBF, ok := mergedAlert.Extension.(messages.BuildFailure)
		if !ok {
			logging.Errorf(ctx, "Couldn't cast extension as BuildFailure: %s", mergedAlert.Type)
		}

		firstFailingBuild := mergedBF
		for _, alr := range keyedAlerts[1:] {
			if alr.Title != mergedAlert.Title {
				// Sanity checking.
				logging.Errorf(ctx, "Merging alerts with same key (%q), different title: (%q vs %q)", key, alr.Title, mergedAlert.Title)
				continue
			}
			bf, ok := alr.Extension.(messages.BuildFailure)
			if !ok {
				logging.Errorf(ctx, "Couldn't cast a %q extension as BuildFailure", alr.Type)
				continue
			}
			// At this point, there should only be one builder per failure because
			// alert keys include the builder name.  We merge builders by step failure
			// in another pass, after this function is called.
			if len(bf.Builders) != 1 {
				logging.Errorf(ctx, "bf.Builders len is not 1: %d", len(bf.Builders))
			}
			firstBuilder := bf.Builders[0]
			mergedBuilder := mergedBF.Builders[0]

			// These failure numbers are build numbers. The UI should probably indicate
			// git numberer sequence numbers instead or in addition to build numbers.

			// FIXME: Use timestamps or revision info instead of build numbers, in
			// case of a master restart.
			if firstBuilder.FirstFailure < mergedBuilder.FirstFailure {
				mergedBuilder.FirstFailure = firstBuilder.FirstFailure
				firstFailingBuild = bf
			}
			if firstBuilder.LatestFailure > mergedBuilder.LatestFailure {
				mergedBuilder.LatestFailure = firstBuilder.LatestFailure
			}
			if firstBuilder.StartTime < mergedBuilder.StartTime || mergedBuilder.StartTime == 0 {
				mergedBuilder.StartTime = firstBuilder.StartTime
			}
			mergedBuilder.Count += firstBuilder.Count
			mergedBF.Builders[0] = mergedBuilder
		}

		mergedBF.RegressionRanges = firstFailingBuild.RegressionRanges

		// Necessary for test cases to be repeatable.
		sort.Sort(regrange.ByRepo(mergedBF.RegressionRanges))

		// FIXME: This is a very simplistic model, and we're throwing away a lot of the findit data.
		// This data should really be a part of the regression range data.
		for _, result := range finditResults {
			if result.StepName != mergedBF.StepAtFault.Step.Name {
				continue
			}

			mergedBF.SuspectedCLs = append(mergedBF.SuspectedCLs, result.SuspectedCLs...)
			mergedBF.FinditStatus = result.TryJobStatus
			mergedBF.HasFindings = result.HasFindings
			mergedBF.IsFinished = result.IsFinished
			mergedBF.IsSupported = result.IsSupported

			buildNumberInURL := result.FirstKnownFailedBuildNumber
			if buildNumberInURL == 0 {
				// If Findit analysis is still running, result.FirstKnownFailedBuildNumber may be empty.
				buildNumberInURL = result.BuildNumber
			}
			buildURL := client.BuildURL(master, builderName, buildNumberInURL).String()
			mergedBF.FinditURL = fmt.Sprintf("https://findit-for-me.appspot.com/waterfall/build-failure?url=%s", buildURL)
		}

		mergedAlert.Extension = mergedBF

		for i, failingBuilder := range mergedBF.Builders {
			if firstSuccessfulBuild != -1 {
				mergedBF.Builders[i].LatestPassing = firstSuccessfulBuild
			}
			if failingBuilder.LatestFailure-failingBuilder.FirstFailure > 0 {
				mergedAlert.Severity = messages.ReliableFailure
			}
			if failingBuilder.StartTime < mergedAlert.StartTime || mergedAlert.StartTime == 0 {
				mergedAlert.StartTime = failingBuilder.StartTime
			}
		}

		alerts = append(alerts, *mergedAlert)
	}

	return alerts, errs
}

func uniques(s []string) []string {
	m := map[string]bool{}
	for _, s := range s {
		m[s] = true
	}

	ret := []string{}
	for k := range m {
		ret = append(ret, k)
	}
	sort.Strings(ret)
	return ret
}

func (a *Analyzer) findImportantFailures(ctx context.Context, master *messages.MasterLocation, builderName string, recentBuildIDs []int64) ([]*messages.BuildStep, error) {
	if !strings.HasPrefix(master.Name(), "official") {
		latestBuild := recentBuildIDs[0]
		importantFailures, err := a.stepFailures(ctx, master, builderName, latestBuild)
		if err != nil {
			return nil, err
		}
		if len(importantFailures) == 0 {
			return nil, nil
		}

		return importantFailures, nil
	}

	return a.officialImportantFailures(ctx, master, builderName, recentBuildIDs)
}

// stepFailures returns the steps that have failed recently on builder builderName.
func (a *Analyzer) stepFailures(ctx context.Context, master *messages.MasterLocation, builderName string, bID int64) ([]*messages.BuildStep, error) {
	var err error // To avoid re-scoping b in the nested conditional below with a :=.
	b, err := client.Build(ctx, master, builderName, bID)
	if err != nil || b == nil {
		logging.Errorf(ctx, "Error fetching build %s/%s/%d: %v", master, builderName, bID, err)
		return nil, err
	}

	ret := []*messages.BuildStep{}

	for _, s := range b.Steps {
		if !s.IsFinished || len(s.Results) == 0 {
			continue
		}

		ok, err := s.IsOK()
		if err != nil {
			logging.Errorf(ctx, err.Error())
		}
		if ok {
			continue
		}
		// We have a failure of some kind, so queue it up to check later.
		// Done so below reference doesn't point to the last element in this loop
		s := s
		ret = append(ret, &messages.BuildStep{
			Master: master,
			Build:  b,
			Step:   &s,
		})
	}

	return ret, nil
}

// stepFailureAlerts returns alerts generated from step failures. It applies filtering
// logic specified in the gatekeeper config to ignore some failures.
func (a *Analyzer) stepFailureAlerts(ctx context.Context, tree string, failures []*messages.BuildStep, finditResults []*messages.FinditResult) ([]messages.Alert, error) {
	filteredFailures := []*messages.BuildStep{}

	for _, failure := range failures {
		if failure.Step.Name == "steps" || failure.Step.Name == "Failure reason" {
			// for "steps", The actual breaking step will appear later.
			// "Failure reason" is an extra step emitted by the recipe engine, when a build fails. It can be ignored.
			continue
		}

		// Check the gatekeeper configs to see if this is ignorable.
		if a.Gatekeeper.ExcludeFailure(ctx, tree, failure.Master, failure.Build.BuilderName, failure.Step.Name) {
			continue
		}

		filteredFailures = append(filteredFailures, failure)
	}
	ret := []messages.Alert{}
	type res struct {
		f   *messages.BuildStep
		a   *messages.Alert
		err error
	}

	// Might not need full capacity buffer, since some failures are ignored below.
	rs := make(chan res, len(filteredFailures))
	reasons := a.reasonFinder(ctx, filteredFailures)

	wg := sync.WaitGroup{}
	scannedFailures := []*messages.BuildStep{}
	for i, failure := range filteredFailures {
		scannedFailures = append(scannedFailures, failure)
		i := i
		failure := failure
		wg.Add(1)
		go func() {
			defer wg.Done()
			if len(failure.Step.Results) > 0 {
				// Check results to see if it's an array of [4]
				// That's a purple failure, which should go to infra/trooper.
				// TODO(martiniss): move this logic into package step
				r, _ := failure.Step.Result()
				if r == messages.ResultInfraFailure {
					logging.Debugf(ctx, "INFRA FAILURE: %s/%s/%s", failure.Master.Name(), failure.Build.BuilderName, failure.Step.Name)
					bf := messages.BuildFailure{
						Builders: []messages.AlertedBuilder{
							{
								Name:          failure.Build.BuilderName,
								URL:           client.BuilderURL(failure.Master, failure.Build.BuilderName).String(),
								StartTime:     failure.Build.Times[0],
								FirstFailure:  failure.Build.Number,
								LatestFailure: failure.Build.Number,
								Master:        failure.Build.Master,
							},
						},
						TreeCloser:  a.Gatekeeper.WouldCloseTree(ctx, failure.Master, failure.Build.BuilderName, failure.Step.Name),
						Reason:      &messages.Reason{Raw: reasons[i]},
						StepAtFault: failure,
					}

					alr := messages.Alert{
						Title:     fmt.Sprintf("%s failing on %s/%s", failure.Step.Name, failure.Master.Name(), failure.Build.BuilderName),
						Body:      "infrastructure failure",
						Type:      messages.AlertInfraFailure,
						StartTime: failure.Build.Times[0],
						Time:      failure.Build.Times[0],
						Severity:  messages.InfraFailure,
						Key:       alertKey(failure.Master.Name(), failure.Build.BuilderName, failure.Step.Name, fmt.Sprintf("%v", failure.Step.Results[0])),
						Extension: bf,
					}

					rs <- res{
						f:   failure,
						a:   &alr,
						err: nil,
					}
					return
				}
			}
			expvars.Add("StepFailures", 1)
			defer expvars.Add("StepFailures", -1)

			alr := messages.Alert{
				Body:      "",
				Time:      failure.Build.Times[0],
				StartTime: failure.Build.Times[0],
				Severity:  messages.NewFailure,
			}

			allowedSet := stringset.NewFromSlice(allowedLinkHosts...)
			for name, href := range failure.Step.Links {
				URL, err := url.Parse(href)
				if err != nil {
					logging.Warningf(ctx, "Failed to parse step link %s: %s", href, err)
					continue
				}
				if !allowedSet.Has(URL.Host) {
					logging.Debugf(ctx, "Step link not in whitelist: %s", href)
					break
				}

				alr.Links = append(alr.Links, messages.Link{
					Title: name,
					Href:  href,
				})
			}

			regRanges := a.regrangeFinder(failure.Build)
			// Read Findit results and add information to the revisions that Findit suspects.
			if len(finditResults) != 0 {
				finditSuspectedCLs := map[string][]*messages.SuspectCL{}
				saveFinditResultInMap(finditResults, failure.Step.Name, finditSuspectedCLs)

				// Add Findit results to regression ranges.
				// There are only the first and last revisions in regRange.Revisions,
				// regRange.RevisionsWithResults will have more if Findit found some culprits within the range.
				for _, regRange := range regRanges {
					revisionsWithResults := []messages.RevisionWithFinditResult{}
					repo := regRange.Repo
					cls, ok := finditSuspectedCLs[repo]
					if ok {
						for _, cl := range cls {
							revisionWithResult := messages.RevisionWithFinditResult{
								Revision:         cl.Revision,
								IsSuspect:        true,
								AnalysisApproach: cl.AnalysisApproach,
								Confidence:       cl.Confidence,
							}
							revisionsWithResults = append(revisionsWithResults, revisionWithResult)
						}
						// Sort the results to display
						regRange.RevisionsWithResults = revisionsWithResults
					}
				}
			}

			for _, change := range failure.Build.SourceStamp.Changes {
				branch, pos, err := change.CommitPosition()
				if err != nil {
					logging.Errorf(ctx, "while getting commit position for %v: %s", change, err)
					continue
				}
				a.rslck.Lock()
				a.revisionSummaries[change.Revision] = messages.RevisionSummary{
					GitHash:     change.Revision,
					Link:        change.Revlink,
					Description: trunc(change.Comments),
					Author:      change.Who,
					When:        change.When,
					Position:    pos,
					Branch:      branch,
				}
				a.rslck.Unlock()
			}

			// If the builder has been failing on the same step for multiple builds in a row,
			// we should have only one alert but indicate the range of builds affected.
			// These are set in FirstFailure and LastFailure.
			bf := messages.BuildFailure{
				Builders: []messages.AlertedBuilder{
					{
						Name:          failure.Build.BuilderName,
						URL:           client.BuilderURL(failure.Master, failure.Build.BuilderName).String(),
						StartTime:     failure.Build.Times[0],
						FirstFailure:  failure.Build.Number,
						LatestFailure: failure.Build.Number,
						Master:        failure.Build.Master,
						Count:         1,
					},
				},
				TreeCloser:       a.Gatekeeper.WouldCloseTree(ctx, failure.Master, failure.Build.BuilderName, failure.Step.Name),
				RegressionRanges: regRanges,
				StepAtFault:      failure,
			}

			if bf.TreeCloser {
				alr.Severity = messages.TreeCloser
			}
			bf.Reason = &messages.Reason{Raw: reasons[i]}

			alr.Title = reasons[i].Title([]*messages.BuildStep{failure})
			reasonSeverity := reasons[i].Severity()
			if reasonSeverity != messages.NoSeverity {
				alr.Severity = reasonSeverity
			}

			alr.Type = messages.AlertBuildFailure
			alr.Key = alertKey(failure.Master.Name(), failure.Build.BuilderName, step.GetTestSuite(failure), "")
			alr.Extension = bf

			rs <- res{
				f:   failure,
				a:   &alr,
				err: nil,
			}
		}()
	}

	doneProcessing := make(chan bool)
	go func() {
		wg.Wait()
		close(rs)
		doneProcessing <- true
	}()

	// This is a 2 phase result collection process. In this phase, we collect
	// results from the channel, until we receive a value from the t channel.
	// When we receieve a value from that, all the alerts have been created,
	// and the rs channel is closed, so we just read everything left over from
	// that.
	//
	// We can't start out doing that because it's possible that there will be
	// more alerts than the number of failed steps, since we can potentially
	// split up steps into multiple alerts. So, we read some of the alerts
	// out of the channel, until all the alerts have been created.
Loop:
	for {
		select {
		case r := <-rs:
			if r.a != nil {
				ret = append(ret, *r.a)
			}
		case <-doneProcessing:
			break Loop
		}
	}
	for r := range rs {
		if r.a != nil {
			ret = append(ret, *r.a)
		}

	}

	return ret, nil
}

func trunc(s string) string {
	if len(s) < 100 {
		return s
	}
	return s[:100]
}

func saveFinditResultInMap(finditResults []*messages.FinditResult, stepName string, finditSuspectedCLs map[string][]*messages.SuspectCL) {
	for _, result := range finditResults {
		for _, cl := range result.SuspectedCLs {
			if result.StepName == stepName {
				finditSuspectedCLs[cl.RepoName] = append(finditSuspectedCLs[cl.RepoName], &cl)
			}
		}
	}
}
