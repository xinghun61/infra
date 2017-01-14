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

	"infra/monitoring/analyzer/regrange"
	"infra/monitoring/analyzer/step"
	"infra/monitoring/client"
	"infra/monitoring/messages"

	"github.com/luci/luci-go/common/data/stringset"
	"github.com/luci/luci-go/common/logging"
)

const (
	// StepCompletedRun is a synthetic step name used to indicate the build run is complete.
	StepCompletedRun = "completed run"

	// Step result values.
	resInfraFailure = float64(4)
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

	// TODO: get a list of all the running builds from be.Slaves? It
	// appears to be used later on in the original py.
	scannedBuilders := []string{}
	for builderName, builder := range be.Builders {
		if a.BuilderOnly != "" && builderName != a.BuilderOnly {
			continue
		}
		scannedBuilders = append(scannedBuilders, builderName)
		go func(builderName string, b messages.Builder) {
			out := r{builderName: builderName, b: b}
			defer func() {
				c <- out
			}()

			expvars.Add("BuilderAlerts", 1)
			defer expvars.Add("BuilderAlerts", -1)
			// Each call to builderAlerts may trigger blocking json fetches,
			// but it has a data dependency on the above cache-warming call, so
			// the logic remains serial.
			out.alerts, out.err = a.builderAlerts(ctx, tree, master, builderName, &b)
		}(builderName, builder)
	}

	ret := []messages.Alert{}
	for _, builderName := range scannedBuilders {
		r := <-c
		if len(r.err) != 0 {
			// TODO: add a special alert for this too?
			logging.Errorf(ctx, "Error getting alerts for builder %s: %v", builderName, r.err)
		} else {
			ret = append(ret, r.alerts...)
		}
	}

	ret = a.mergeAlertsByReason(ctx, ret)

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

// mergeAlertsByReason merges alerts for step failures occurring across multiple builders into
// one alert with multiple builders indicated.
// FIXME: Move the regression range logic into package regrange
func (a *Analyzer) mergeAlertsByReason(ctx context.Context, alerts []messages.Alert) []messages.Alert {
	mergedAlerts := []messages.Alert{}
	byReason := map[string][]messages.Alert{}
	for _, alert := range alerts {
		bf, ok := alert.Extension.(messages.BuildFailure)
		if !ok {
			logging.Infof(ctx, "%s failed, but isn't a builder-failure: %s", alert.Key, alert.Type)
			// Not a builder failure, so don't bother trying to group it by step name.
			mergedAlerts = append(mergedAlerts, alert)
			continue
		}
		r := bf.Reason
		k := r.Kind() + "|" + r.Signature()
		byReason[k] = append(byReason[k], alert)
	}

	sortedReasons := []string{}
	for reason := range byReason {
		sortedReasons = append(sortedReasons, reason)
	}

	sort.Strings(sortedReasons)

	// Merge build failures by step, then make a single alert listing all of the builders
	// failing for that step.
	for _, reason := range sortedReasons {
		stepAlerts := byReason[reason]
		if len(stepAlerts) == 1 {
			mergedAlerts = append(mergedAlerts, stepAlerts[0])
			continue
		}

		sort.Sort(messages.Alerts(stepAlerts))
		merged := stepAlerts[0]

		mergedBF := merged.Extension.(messages.BuildFailure)
		if len(mergedBF.Builders) > 1 {
			logging.Errorf(ctx, "Alert shouldn't have multiple builders before merging by reason: %+v", reason)
		}

		stepsAtFault := make([]*messages.BuildStep, len(stepAlerts))
		for i := range stepAlerts {
			bf, ok := stepAlerts[i].Extension.(messages.BuildFailure)
			if !ok {
				continue
			}

			stepsAtFault[i] = bf.StepAtFault
		}
		merged.Title = mergedBF.Reason.Title(stepsAtFault)

		// Clear out the list of builders because we're going to reconstruct it.
		mergedBF.Builders = []messages.AlertedBuilder{}
		mergedBF.RegressionRanges = []*messages.RegressionRange{}

		builders := map[string]messages.AlertedBuilder{}
		regressionRanges := map[string][]*messages.RegressionRange{}

		for _, alert := range stepAlerts { // stepAlerts[1:]? already have [0] in mergedBf
			bf := alert.Extension.(messages.BuildFailure)
			if len(bf.Builders) > 1 {
				logging.Errorf(ctx, "Alert shouldn't have multiple builders before merging by reason: %+v", reason)
			}
			if bf.TreeCloser {
				mergedBF.TreeCloser = true
			}

			builder := bf.Builders[0]
			// If any of the builders would call it a tree closer,
			// mark the merged alert as one.
			mergedBF.TreeCloser = bf.TreeCloser || mergedBF.TreeCloser
			if ab, ok := builders[builder.Name]; ok {
				if ab.FirstFailure < builder.FirstFailure {
					builder.FirstFailure = ab.FirstFailure
				}
				if ab.LatestFailure > builder.LatestFailure {
					builder.LatestFailure = ab.LatestFailure
				}
				if ab.StartTime < builder.StartTime || builder.StartTime == 0 {
					builder.StartTime = ab.StartTime
				}
			}
			builders[builder.Name] = builder
			regressionRanges[builder.Name] = bf.RegressionRanges
		}

		builderNames := []string{}
		for name := range builders {
			builderNames = append(builderNames, name)
		}
		sort.Strings(builderNames)

		for _, name := range builderNames {
			builder := builders[name]
			mergedBF.Builders = append(mergedBF.Builders, builder)
			// Fix this so it de-dupes regression ranges, or at least dedupes the Revisions in
			// in each repo.
			mergedBF.RegressionRanges = append(mergedBF.RegressionRanges, regressionRanges[builder.Name]...)
		}

		// De-dupe regression ranges by repo.
		posByRepo := map[string][]string{}
		for _, regRange := range mergedBF.RegressionRanges {
			posByRepo[regRange.Repo] = append(posByRepo[regRange.Repo], regRange.Positions...)
		}

		mergedBF.RegressionRanges = []*messages.RegressionRange{}
		for repo, pos := range posByRepo {
			mergedBF.RegressionRanges = append(mergedBF.RegressionRanges, &messages.RegressionRange{
				Repo:      repo,
				Positions: uniques(pos),
			})
		}

		sort.Sort(regrange.ByRepo(mergedBF.RegressionRanges))

		if len(mergedBF.Builders) > 1 {
			builderNames := []string{}
			for _, b := range mergedBF.Builders {
				builderNames = append(builderNames, b.Name)
				if b.StartTime < merged.StartTime || merged.StartTime == 0 {
					merged.StartTime = b.StartTime
				}
			}
			merged.Body = strings.Join(builderNames, ", ")
		}

		shrunkRegressionRanges := []*messages.RegressionRange{}

		// Save space for long commit position lists by just keeping the first and last.
		for _, r := range mergedBF.RegressionRanges {
			if len(r.Positions) > 2 {
				r.Positions = []string{r.Positions[0], r.Positions[len(r.Positions)-1]}
			}
			shrunkRegressionRanges = append(shrunkRegressionRanges, r)
		}
		mergedBF.RegressionRanges = shrunkRegressionRanges

		merged.Extension = mergedBF
		mergedAlerts = append(mergedAlerts, merged)
	}

	return mergedAlerts
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
	stepAlertsByKey := map[string][]messages.Alert{}

	importantFailures, err := a.findImportantFailures(ctx, master, builderName, recentBuildIDs)

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
	finditResults, err := client.Findit(ctx, master, builderName, latestBuild, stepNames)
	if err != nil {
		logging.Errorf(ctx, "while getting findit results for build: %s", err)
	}

	for _, buildNum := range recentBuildIDs {
		failures, err := a.stepFailures(ctx, master, builderName, buildNum)
		if err != nil {
			errs = append(errs, err)
		}
		if len(failures) == 0 {
			// Bail as soon as we find a successful build.
			break
		}

		fResults := []*messages.FinditResult{}
		if buildNum == latestBuild {
			fResults = finditResults
		} else {
			// Get findit results for other build.
			f, err := client.Findit(ctx, master, builderName, buildNum, []string{})
			if err != nil {
				logging.Errorf(ctx, "while getting findit results for build: %s", err)
			} else {
				fResults = f
			}
		}
		as, err := a.stepFailureAlerts(ctx, tree, failures, fResults)
		if err != nil {
			errs = append(errs, err)
		}

		// Group alerts by key so they can be merged across builds/regression ranges.
		for _, alr := range as {
			if importantKeys.Has(alr.Key) {
				stepAlertsByKey[alr.Key] = append(stepAlertsByKey[alr.Key], alr)
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
			// gnumbd sequence numbers instead or in addition to build numbers.

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

			buildURL := client.BuildURL(master, builderName, result.FirstKnownFailedBuildNumber).String()
			mergedBF.FinditURL = fmt.Sprintf("https://findit-for-me.appspot.com/waterfall/build-failure?url=%s", buildURL)
		}

		mergedAlert.Extension = mergedBF

		for _, failingBuilder := range mergedBF.Builders {
			if failingBuilder.LatestFailure-failingBuilder.FirstFailure > 0 {
				mergedAlert.Severity = messages.ReliableFailure
			}
			if failingBuilder.StartTime < mergedAlert.StartTime || mergedAlert.StartTime == 0 {
				mergedAlert.StartTime = failingBuilder.StartTime
			}
		}

		alerts = append(alerts, mergedAlert)
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
		if failure.Step.Name == "steps" {
			// The actual breaking step will appear later.
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

	scannedFailures := []*messages.BuildStep{}
	for i, failure := range filteredFailures {
		if len(failure.Step.Results) > 0 {
			// Check results to see if it's an array of [4]
			// That's a purple failure, which should go to infra/trooper.
			// TODO(martiniss): move this logic into package step
			r, _ := failure.Step.Result()
			if r == messages.ResultInfraFailure {
				logging.Infof(ctx, "INFRA FAILURE: %s/%s/%s", failure.Master.Name(), failure.Build.BuilderName, failure.Step.Name)
				bf := messages.BuildFailure{
					Builders: []messages.AlertedBuilder{
						{
							Name:          failure.Build.BuilderName,
							URL:           client.BuilderURL(failure.Master, failure.Build.BuilderName).String(),
							StartTime:     failure.Build.Times[0],
							FirstFailure:  failure.Build.Number,
							LatestFailure: failure.Build.Number,
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

				scannedFailures = append(scannedFailures, failure)
				rs <- res{
					f:   failure,
					a:   &alr,
					err: nil,
				}
				continue
			}
		}
		scannedFailures = append(scannedFailures, failure)
		i := i
		f := failure
		go func() {
			expvars.Add("StepFailures", 1)
			defer expvars.Add("StepFailures", -1)

			alr := messages.Alert{
				Body:      "",
				Time:      f.Build.Times[0],
				StartTime: f.Build.Times[0],
				Severity:  messages.NewFailure,
			}

			allowedSet := stringset.NewFromSlice(allowedLinkHosts...)
			for name, href := range f.Step.Links {
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

			regRanges := a.regrangeFinder(f.Build)
			// Read Findit results and add information to the revisions that Findit suspects.
			if len(finditResults) != 0 {
				finditSuspectedCLs := map[string][]*messages.SuspectCL{}
				saveFinditResultInMap(finditResults, f.Step.Name, finditSuspectedCLs)

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

			for _, change := range f.Build.SourceStamp.Changes {
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
						Name:          f.Build.BuilderName,
						URL:           client.BuilderURL(f.Master, f.Build.BuilderName).String(),
						StartTime:     f.Build.Times[0],
						FirstFailure:  f.Build.Number,
						LatestFailure: f.Build.Number,
					},
				},
				TreeCloser:       a.Gatekeeper.WouldCloseTree(ctx, f.Master, f.Build.BuilderName, f.Step.Name),
				RegressionRanges: regRanges,
				StepAtFault:      f,
			}

			if bf.TreeCloser {
				alr.Severity = messages.TreeCloser
			}
			bf.Reason = &messages.Reason{Raw: reasons[i]}

			alr.Title = reasons[i].Title([]*messages.BuildStep{f})
			reasonSeverity := reasons[i].Severity()
			if reasonSeverity != messages.NoSeverity {
				alr.Severity = reasonSeverity
			}

			alr.Type = messages.AlertBuildFailure
			alr.Key = alertKey(f.Master.Name(), f.Build.BuilderName, step.GetTestSuite(f), "")
			alr.Extension = bf

			rs <- res{
				f:   f,
				a:   &alr,
				err: nil,
			}
		}()
	}

	for range filteredFailures {
		r := <-rs
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
