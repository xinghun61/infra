// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyzer

import (
	"errors"
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/luci/luci-go/common/logging/gologger"

	"infra/monitoring/client"
	"infra/monitoring/messages"
)

const (
	// StepCompletedRun is a synthetic step name used to indicate the build run is complete.
	StepCompletedRun   = "completed run"
	treeCloserPri      = 0
	reliableFailureSev = 0
	newFailureSev      = 1
	staleMasterSev     = 0
	staleBuilderSev    = 0
	hungBuilderSev     = 1
	idleBuilderSev     = 1
	offlineBuilderSev  = 1
	resOK              = float64(1)
	resInfraFailure    = float64(4)
)

var (
	log = gologger.Get()
)

var (
	errNoBuildSteps      = errors.New("No build steps")
	errNoRecentBuilds    = errors.New("No recent builds")
	errNoCompletedBuilds = errors.New("No completed builds")
)

// StepAnalyzer reasons about a stepFailure and produces a set of reasons for the
// failure.  It also indicates whether or not it recognizes the stepFailure.
type StepAnalyzer interface {
	// Analyze returns a list of reasons for the step failure, and a boolean
	// value indicating whether or not the step failure was recognized by
	// the analyzer.
	Analyze(f stepFailure) (*StepAnalyzerResult, error)
}

// StepAnalyzerResult is the result of running analysis on a stepFailure.
type StepAnalyzerResult struct {
	// Recognized is true if the StepFailureAnalyzer recognized the stepFailure.
	Recognized bool

	// Reasons lists the reasons for the stepFailure determined by the StepFailureAnalyzer.
	Reasons []string
}

// Analyzer runs the process of checking masters, builders, test results and so on,
// in order to produce alerts.
type Analyzer struct {
	// MaxRecentBuilds is the maximum number of recent builds to check, per builder.
	MaxRecentBuilds int

	// MinRecentBuilds is the minimum number of recent builds to check, per builder.
	MinRecentBuilds int

	// StepAnalzers are the set of build step failure analyzers to be checked on
	// build step failures.
	StepAnalyzers []StepAnalyzer

	// Reader is the Reader implementation for fetching json from CBE, builds, etc.
	Reader client.Reader

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

	// MasterCfgs is a map of master name to MasterConfig
	MasterCfgs map[string]messages.MasterConfig

	// These limit the scope analysis, useful for debugging.
	MasterOnly  string
	BuilderOnly string
	BuildOnly   int64

	revisionSummaries map[string]messages.RevisionSummary

	// Now is useful for mocking the system clock in testing and simulating time
	// during replay.
	Now func() time.Time
}

// New returns a new Analyzer. If client is nil, it assigns a default implementation.
// maxBuilds is the maximum number of builds to check, per builder.
func New(c client.Reader, minBuilds, maxBuilds int) *Analyzer {
	if c == nil {
		c = client.NewReader()
	}

	return &Analyzer{
		Reader:                 c,
		MaxRecentBuilds:        maxBuilds,
		MinRecentBuilds:        minBuilds,
		HungBuilderThresh:      3 * time.Hour,
		OfflineBuilderThresh:   90 * time.Minute,
		IdleBuilderCountThresh: 50,
		StaleMasterThreshold:   10 * time.Minute,
		StepAnalyzers: []StepAnalyzer{
			&TestFailureAnalyzer{Reader: c},
			&CompileFailureAnalyzer{Reader: c},
		},
		MasterCfgs: map[string]messages.MasterConfig{},

		revisionSummaries: map[string]messages.RevisionSummary{},
		Now: func() time.Time {
			return time.Now()
		},
	}
}

// MasterAlerts returns alerts generated from the master.
func (a *Analyzer) MasterAlerts(master string, be *messages.BuildExtract) []messages.Alert {
	ret := []messages.Alert{}

	// Copied logic from builder_messages.
	// No created_timestamp should be a warning sign, no?
	if be.CreatedTimestamp == messages.EpochTime(0) {
		return ret
	}

	elapsed := a.Now().Sub(be.CreatedTimestamp.Time())
	if elapsed > a.StaleMasterThreshold {
		ret = append(ret, messages.Alert{
			Key:       fmt.Sprintf("stale master: %v", master),
			Title:     fmt.Sprintf("Stale %s master data", master),
			Body:      fmt.Sprintf("%s elapsed since last update.", elapsed),
			StartTime: messages.TimeToEpochTime(be.CreatedTimestamp.Time()),
			Severity:  staleMasterSev,
			Time:      messages.TimeToEpochTime(a.Now()),
			Links:     []messages.Link{{"Master", client.MasterURL(master)}},
			// No type or extension for now.
		})
	}
	if elapsed < 0 {
		// Add this to the alerts returned, rather than just log it?
		log.Errorf("Master %s timestamp is newer than current time (%s): %s old.", master, a.Now(), elapsed)
	}

	return ret
}

// BuilderAlerts returns alerts generated from builders connected to the master.
func (a *Analyzer) BuilderAlerts(masterName string, be *messages.BuildExtract) []messages.Alert {
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

			// Each call to builderAlerts may trigger blocking json fetches,
			// but it has a data dependency on the above cache-warming call, so
			// the logic remains serial.
			out.alerts, out.err = a.builderAlerts(masterName, builderName, &b)
		}(builderName, builder)
	}

	ret := []messages.Alert{}
	for _, builderName := range scannedBuilders {
		r := <-c
		if len(r.err) != 0 {
			// TODO: add a special alert for this too?
			log.Errorf("Error getting alerts for builder %s: %v", builderName, r.err)
		} else {
			ret = append(ret, r.alerts...)
		}
	}

	ret = a.mergeAlertsByStep(ret)
	return ret
}

// TODO: actually write the on-disk cache.
func filenameForCacheKey(cc string) string {
	cc = strings.Replace(cc, "/", "_", -1)
	return fmt.Sprintf("/tmp/dispatcher.cache/%s", cc)
}

func alertKey(master, builder, step string) string {
	return fmt.Sprintf("%s.%s.%s", master, builder, step)
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
func (a *Analyzer) lastBuilds(masterName, builderName string, recentBuildIDs []int64) (lastBuild, lastCompletedBuild *messages.Build, err error) {
	// Check for stale/idle/offline builders.  Latest build is the first in the list.

	for i, buildNum := range recentBuildIDs {
		log.Infof("Checking last %s/%s build ID: %d", masterName, builderName, buildNum)

		var build *messages.Build
		build, err = a.Reader.Build(masterName, builderName, buildNum)
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
func (a *Analyzer) builderAlerts(masterName string, builderName string, b *messages.Builder) ([]messages.Alert, []error) {
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

	lastBuild, lastCompletedBuild, err := a.lastBuilds(masterName, builderName, recentBuildIDs)
	if err != nil {
		errs = append(errs, err)
		return nil, errs
	}

	// Examining only the latest build is probably suboptimal since if it's still in progress it might
	// not have hit a step that is going to fail and has failed repeatedly for the last few builds.
	// AKA "Reliable failures".  TODO: Identify "Reliable failures"
	lastStep, lastUpdated, err := a.latestBuildStep(lastBuild)
	if err != nil {
		errs = append(errs, fmt.Errorf("Couldn't get latest build step for %s.%s: %v", masterName, builderName, err))
		return alerts, errs
	}
	elapsed := a.Now().Sub(lastUpdated.Time())
	links := []messages.Link{
		{"Builder", client.BuilderURL(masterName, builderName)},
		{"Last build", client.BuildURL(masterName, builderName, lastBuild.Number)},
		{"Last build step", client.StepURL(masterName, builderName, lastStep, lastBuild.Number)},
	}

	switch b.State {
	case messages.StateBuilding:
		if elapsed > a.HungBuilderThresh && lastStep != StepCompletedRun {
			alerts = append(alerts, messages.Alert{
				Key:      fmt.Sprintf("%s.%s.hung", masterName, builderName),
				Title:    fmt.Sprintf("%s.%s is hung in step %s.", masterName, builderName, lastStep),
				Body:     fmt.Sprintf("%s.%s has been building for %v (last step update %s), past the alerting threshold of %v", masterName, builderName, elapsed, lastUpdated.Time(), a.HungBuilderThresh),
				Severity: hungBuilderSev,
				Time:     messages.TimeToEpochTime(a.Now()),
				Links:    links,
			})
			// Note, just because it's building doesn't mean it's in a good state. If the last N builds
			// all failed (for some large N) then this might still be alertable.
		}
	case messages.StateOffline:
		if elapsed > a.OfflineBuilderThresh {
			alerts = append(alerts, messages.Alert{
				Key:      fmt.Sprintf("%s.%s.offline", masterName, builderName),
				Title:    fmt.Sprintf("%s.%s is offline.", masterName, builderName),
				Body:     fmt.Sprintf("%s.%s has been offline for %v (last step update %s %v), past the alerting threshold of %v", masterName, builderName, elapsed, lastUpdated.Time(), float64(lastUpdated), a.OfflineBuilderThresh),
				Severity: offlineBuilderSev,
				Time:     messages.TimeToEpochTime(a.Now()),
				Links:    links,
			})
		}
	case messages.StateIdle:
		if b.PendingBuilds > a.IdleBuilderCountThresh {
			alerts = append(alerts, messages.Alert{
				Key:      fmt.Sprintf("%s.%s.idle", masterName, builderName),
				Title:    fmt.Sprintf("%s.%s is idle with too many pending builds.", masterName, builderName),
				Body:     fmt.Sprintf("%s.%s is idle with %d pending builds, past the alerting threshold of %d", masterName, builderName, b.PendingBuilds, a.IdleBuilderCountThresh),
				Severity: idleBuilderSev,
				Time:     messages.TimeToEpochTime(a.Now()),
				Links:    links,
			})
		}
	default:
		log.Errorf("Unknown %s.%s builder state: %s", masterName, builderName, b.State)
	}

	// Check for alerts on the most recent complete build
	log.Infof("Checking %d most recent builds for alertable step failures: %s/%s", len(recentBuildIDs), masterName, builderName)
	as, es := a.builderStepAlerts(masterName, builderName, []int64{lastCompletedBuild.Number})

	if len(as) > 0 {
		mostRecentComplete := 0
		for i, id := range recentBuildIDs {
			if id == lastCompletedBuild.Number {
				mostRecentComplete = i
			}
		}
		as, es = a.builderStepAlerts(masterName, builderName, recentBuildIDs[mostRecentComplete:])
		alerts = append(alerts, as...)
		errs = append(errs, es...)
	}

	return alerts, errs
}

// mergeAlertsByStep merges alerts for step failures occurring across multiple builders into
// one alert with multiple builders indicated.
func (a *Analyzer) mergeAlertsByStep(alerts []messages.Alert) []messages.Alert {
	mergedAlerts := []messages.Alert{}
	byStep := map[string][]messages.Alert{}
	for _, alert := range alerts {
		bf, ok := alert.Extension.(messages.BuildFailure)
		if !ok {
			// Not a builder failure, so don't bother trying to group it by step name.
			mergedAlerts = append(mergedAlerts, alert)
			continue
		}
		for _, r := range bf.Reasons {
			// TODO: also check r.Test?  That might leave too many alerts.
			byStep[r.Step] = append(byStep[r.Step], alert)
		}
	}

	sortedSteps := []string{}
	for step := range byStep {
		sortedSteps = append(sortedSteps, step)
	}

	sort.Strings(sortedSteps)

	// Merge build failures by step, then make a single alert listing all of the builders
	// failing for that step.
	for _, step := range sortedSteps {
		stepAlerts := byStep[step]
		if len(stepAlerts) == 1 {
			mergedAlerts = append(mergedAlerts, stepAlerts[0])
			continue
		}

		merged := stepAlerts[0]

		mergedBF := merged.Extension.(messages.BuildFailure)
		if len(mergedBF.Builders) > 1 {
			log.Errorf("Alert shouldn't have multiple builders before merging by step: %+v", mergedBF)
		}

		// Clear out the list of builders because we're going to reconstruct it.
		mergedBF.Builders = []messages.AlertedBuilder{}
		mergedBF.RegressionRanges = []messages.RegressionRange{}

		builders := map[string]messages.AlertedBuilder{}
		regressionRanges := map[string][]messages.RegressionRange{}

		for _, alert := range stepAlerts {
			bf := alert.Extension.(messages.BuildFailure)
			if len(bf.Builders) > 1 {
				log.Errorf("Alert shouldn't have multiple builders before merging by step: %+v", mergedBF)
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
		revsByRepo := map[string][]string{}
		for _, regRange := range mergedBF.RegressionRanges {
			revsByRepo[regRange.Repo] = append(revsByRepo[regRange.Repo], regRange.Revisions...)
		}
		mergedBF.RegressionRanges = []messages.RegressionRange{}
		for repo, revs := range revsByRepo {
			mergedBF.RegressionRanges = append(mergedBF.RegressionRanges, messages.RegressionRange{
				Repo:      repo,
				Revisions: uniques(revs),
			})
		}

		sort.Sort(byRepo(mergedBF.RegressionRanges))

		if len(mergedBF.Builders) > 1 {
			merged.Title = fmt.Sprintf("%s (failing on %d builders)", step, len(mergedBF.Builders))
		}
		merged.Extension = mergedBF
		mergedAlerts = append(mergedAlerts, merged)
	}

	return mergedAlerts
}

// GetRevisionSummaries returns a slice of RevisionSummaries for the list of hashes.
func (a *Analyzer) GetRevisionSummaries(hashes []string) ([]messages.RevisionSummary, error) {
	ret := []messages.RevisionSummary{}
	for _, h := range hashes {
		s, ok := a.revisionSummaries[h]
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
func (a *Analyzer) builderStepAlerts(masterName, builderName string, recentBuildIDs []int64) (alerts []messages.Alert, errs []error) {
	// Check for alertable step failures.  We group them by key to de-duplicate and merge values
	// once we've scanned everything.
	stepAlertsByKey := map[string][]messages.Alert{}

	for _, buildNum := range recentBuildIDs {
		failures, err := a.stepFailures(masterName, builderName, buildNum)
		if err != nil {
			errs = append(errs, err)
		}
		if len(failures) == 0 {
			// Bail as soon as we find a successful build.
			break
		}

		as, err := a.stepFailureAlerts(failures)
		if err != nil {
			errs = append(errs, err)
		}

		// Group alerts by key so they can be merged across builds/regression ranges.
		for _, alr := range as {
			stepAlertsByKey[alr.Key] = append(stepAlertsByKey[alr.Key], alr)
		}
	}

	// Now coalesce alerts with the same key into single alerts with merged properties.
	for key, keyedAlerts := range stepAlertsByKey {
		log.Infof("Merging %d distinct alerts for key: %q", len(alerts), key)

		mergedAlert := keyedAlerts[0] // Merge everything into the first one
		mergedBF, ok := mergedAlert.Extension.(messages.BuildFailure)
		if !ok {
			log.Errorf("Couldn't cast extension as BuildFailure: %s", mergedAlert.Type)
		}

		for _, alr := range keyedAlerts[1:] {
			if alr.Title != mergedAlert.Title {
				// Sanity checking.
				log.Errorf("Merging alerts with same key (%q), different title: (%q vs %q)", key, alr.Title, mergedAlert.Title)
				continue
			}
			bf, ok := alr.Extension.(messages.BuildFailure)
			if !ok {
				log.Errorf("Couldn't cast a %q extension as BuildFailure", alr.Type)
				continue
			}
			// At this point, there should only be one builder per failure because
			// alert keys include the builder name.  We merge builders by step failure
			// in another pass, after this funtion is called.
			firstBuilder := bf.Builders[0]
			mergedBuilder := mergedBF.Builders[0]
			if firstBuilder.FirstFailure < mergedBuilder.FirstFailure {
				mergedBuilder.FirstFailure = firstBuilder.FirstFailure
			}
			if firstBuilder.LatestFailure > mergedBuilder.LatestFailure {
				mergedBuilder.LatestFailure = firstBuilder.LatestFailure
			}
			if firstBuilder.StartTime < mergedBuilder.StartTime || mergedBuilder.StartTime == 0 {
				mergedBuilder.StartTime = firstBuilder.StartTime
			}
			mergedBF.Builders[0] = mergedBuilder
			// TODO: merge these ranges properly and de-dupe.
			mergedBF.RegressionRanges = append(mergedBF.RegressionRanges, bf.RegressionRanges...)
		}

		// Now merge regression ranges by repo.
		revisionsByRepo := map[string][]string{}
		for _, rr := range mergedBF.RegressionRanges {
			revisionsByRepo[rr.Repo] = append(revisionsByRepo[rr.Repo], rr.Revisions...)
		}

		mergedBF.RegressionRanges = []messages.RegressionRange{}

		for repo, revisions := range revisionsByRepo {
			mergedBF.RegressionRanges = append(mergedBF.RegressionRanges,
				messages.RegressionRange{
					Repo:      repo,
					Revisions: uniques(revisions),
				})
		}

		// Necessary for test cases to be repeatable.
		sort.Sort(byRepo(mergedBF.RegressionRanges))

		mergedAlert.Extension = mergedBF

		for _, failingBuilder := range mergedBF.Builders {
			if failingBuilder.LatestFailure-failingBuilder.FirstFailure > 0 {
				mergedAlert.Severity = reliableFailureSev
			}
			if failingBuilder.StartTime < mergedAlert.StartTime {
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

type byRepo []messages.RegressionRange

func (a byRepo) Len() int           { return len(a) }
func (a byRepo) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }
func (a byRepo) Less(i, j int) bool { return a[i].Repo < a[j].Repo }

// stepFailures returns the steps that have failed recently on builder builderName.
func (a *Analyzer) stepFailures(masterName string, builderName string, bID int64) ([]stepFailure, error) {

	var err error // To avoid re-scoping b in the nested conditional below with a :=.
	b, err := a.Reader.Build(masterName, builderName, bID)
	if err != nil || b == nil {
		log.Errorf("Error fetching build: %v", err)
		return nil, err
	}

	ret := []stepFailure{}

	for _, s := range b.Steps {
		if !s.IsFinished || len(s.Results) == 0 {
			continue
		}
		// Because Results in the json data is a homogeneous array, the unmarshaler
		// doesn't have any type information to assert about it. We have to do
		// some ugly runtime type assertion ourselves.
		if r, ok := s.Results[0].(float64); ok {
			if r <= resOK {
				// This 0/1 check seems to be a convention or heuristic. A 0 or 1
				// result is apparently "ok", accoring to the original python code.
				continue
			}
		} else {
			log.Errorf("Couldn't unmarshal first step result into a float64: %v", s.Results[0])
		}

		// We have a failure of some kind, so queue it up to check later.
		ret = append(ret, stepFailure{
			masterName:  masterName,
			builderName: builderName,
			build:       *b,
			step:        s,
		})
	}

	return ret, nil
}

// stepFailureAlerts returns alerts generated from step failures. It applies filtering
// logic specified in the gatekeeper config to ignore some failures.
func (a *Analyzer) stepFailureAlerts(failures []stepFailure) ([]messages.Alert, error) {
	ret := []messages.Alert{}
	type res struct {
		f   stepFailure
		a   *messages.Alert
		err error
	}

	// Might not need full capacity buffer, since some failures are ignored below.
	rs := make(chan res, len(failures))

	scannedFailures := []stepFailure{}
	for _, failure := range failures {
		// goroutine/channel because the reasonsForFailure call potentially
		// blocks on IO.
		if failure.step.Name == "steps" {
			// check results to see if it's an array of [4]
			// That's a purple failure, which should go to infra/trooper.
			log.Infof("steps results: %+v", failure.step)
			if len(failure.step.Results) > 0 {
				if r, ok := failure.step.Results[0].(float64); ok && r == resInfraFailure {
					// TODO: Create a trooper alert about this.
					log.Errorf("INFRA FAILURE: %+v", failure)
				}
			}
			continue
			// The actual breaking step will appear later.
		}

		// Check the gatekeeper configs to see if this is ignorable.
		if a.excludeFailure(failure.masterName, failure.builderName, failure.step.Name) {
			continue
		}

		scannedFailures = append(scannedFailures, failure)
		go func(f stepFailure) {
			alr := messages.Alert{
				Title: fmt.Sprintf("Builder step failure: %s.%s", f.masterName, f.builderName),
				Time:  messages.EpochTime(a.Now().Unix()),
				Type:  "buildfailure",
			}

			regRanges := []messages.RegressionRange{}
			revisionsByRepo := map[string][]string{}

			for _, change := range f.build.SourceStamp.Changes {
				// check change.Comments for text like
				// "Cr-Commit-Position: refs/heads/master@{#330158}" to pick out revs from git commits.
				revisionsByRepo[change.Repository] = append(revisionsByRepo[change.Repository], change.Revision)

				a.revisionSummaries[change.Revision] = messages.RevisionSummary{
					GitHash:     change.Revision,
					Link:        change.Revlink,
					Description: trunc(change.Comments),
					Author:      change.Who,
					When:        change.When,
				}
			}

			for repo, revisions := range revisionsByRepo {
				regRanges = append(regRanges, messages.RegressionRange{
					Repo:      repo,
					Revisions: revisions,
				})
			}

			// If the builder has been failing on the same step for multiple builds in a row,
			// we should have only one alert but indicate the range of builds affected.
			// These are set in FirstFailure and LastFailure.
			bf := messages.BuildFailure{
				// FIXME: group builders?
				Builders: []messages.AlertedBuilder{
					{
						Name:          f.builderName,
						URL:           client.BuilderURL(f.masterName, f.builderName),
						StartTime:     f.build.CreatedTimestamp,
						FirstFailure:  f.build.Number,
						LatestFailure: f.build.Number,
					},
				},
				TreeCloser:       a.wouldCloseTree(f.masterName, f.builderName, f.step.Name),
				RegressionRanges: regRanges,
			}

			reasons := a.reasonsForFailure(f)
			for _, r := range reasons {
				bf.Reasons = append(bf.Reasons, messages.Reason{
					TestName: r,
					Step:     f.step.Name,
					URL:      f.URL(),
				})
			}

			alr.Key = alertKey(f.masterName, f.builderName, f.step.Name)
			if len(bf.Reasons) == 0 {
				log.Warningf("No reasons for step failure: %s", alr.Key)
				bf.Reasons = append(bf.Reasons, messages.Reason{
					Step: f.step.Name,
					URL:  f.URL(),
				})
			}

			alr.Extension = bf

			rs <- res{
				f:   f,
				a:   &alr,
				err: nil,
			}
		}(failure)
	}

	for range scannedFailures {
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

// reasonsForFailure examines the step failure and applies some heuristics to
// to find the cause. It may make blocking IO calls in the process.
func (a *Analyzer) reasonsForFailure(f stepFailure) []string {
	ret := []string{}
	recognized := false
	log.Infof("Checking for reasons for failure step: %v", f.step.Name)
	for _, sfa := range a.StepAnalyzers {
		res, err := sfa.Analyze(f)
		if err != nil {
			// TODO: return something that contains errors *and* reasons.
			log.Errorf("Error getting reasons from StepAnalyzer: %v", err)
			continue
		}
		if res.Recognized {
			recognized = true
			ret = append(ret, res.Reasons...)
		}
	}

	if !recognized {
		// TODO: log and report frequently encountered unrecognized builder step
		// failure names.
		log.Errorf("Unrecognized step step failure type, unable to find reasons: %s", f.step.Name)
	}

	return ret
}

func (a *Analyzer) excludeFailure(master, builder, step string) bool {
	mc, ok := a.MasterCfgs[master]
	if !ok {
		log.Errorf("Can't filter unknown master %s", master)
		return false
	}

	for _, ebName := range mc.ExcludedBuilders {
		if ebName == "*" || ebName == builder {
			return true
		}
	}

	// Not clear that builder_alerts even looks at the rest of these condtions
	// even though they're specified in gatekeeper.json
	for _, s := range mc.ExcludedSteps {
		if step == s {
			return true
		}
	}

	bc, ok := mc.Builders[builder]
	if !ok {
		if bc, ok = mc.Builders["*"]; !ok {
			log.Warningf("Unknown %s builder %s", master, builder)
			return true
		}
	}

	for _, esName := range bc.ExcludedSteps {
		if esName == step || esName == "*" {
			return true
		}
	}

	return false
}

func (a *Analyzer) wouldCloseTree(master, builder, step string) bool {
	mc, ok := a.MasterCfgs[master]
	if !ok {
		log.Errorf("Missing master cfg: %s", master)
		return false
	}
	bc, ok := mc.Builders[builder]
	if !ok {
		bc, ok = mc.Builders["*"]
		if ok {
			return true
		}
	}

	for _, xstep := range bc.ExcludedSteps {
		if xstep == step {
			return false
		}
	}

	csteps := []string{}
	csteps = append(csteps, bc.ClosingSteps...)
	csteps = append(csteps, bc.ClosingOptional...)

	for _, cs := range csteps {
		if cs == "*" || cs == step {
			return true
		}
	}

	return false
}

// unexpected returns the set of expected xor actual.
func unexpected(expected, actual []string) []string {
	e, a := make(map[string]bool), make(map[string]bool)
	for _, s := range expected {
		e[s] = true
	}
	for _, s := range actual {
		a[s] = true
	}

	ret := []string{}
	for k := range e {
		if !a[k] {
			ret = append(ret, k)
		}
	}

	for k := range a {
		if !e[k] {
			ret = append(ret, k)
		}
	}

	return ret
}

type stepFailure struct {
	masterName  string
	builderName string
	build       messages.Build
	step        messages.Step
}

// URL returns a url to builder step failure page.
func (f stepFailure) URL() string {
	return client.StepURL(f.masterName, f.builderName, f.step.Name, f.build.Number)
}
