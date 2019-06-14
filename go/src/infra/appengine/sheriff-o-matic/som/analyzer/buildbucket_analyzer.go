package analyzer

import (
	"encoding/json"
	"fmt"
	"infra/monitoring/messages"
	"net/url"
	"strings"
	"sync"
	"time"

	bbpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"golang.org/x/net/context"
)

const reasonWorkerPoolSize = 10

func stepSet(s []*bbpb.Step) stringset.Set {
	steps := stringset.New(0)
	for _, step := range s {
		steps.Add(step.Name)
	}

	return steps
}

func builderIDToStr(id *bbpb.BuilderID) string {
	byts, err := json.Marshal(id)
	if err != nil {
		panic(fmt.Sprintf("could not marshal builder ID %+v: %+v", id, err))
	}
	return string(byts)
}

func strToBuilderID(s string) *bbpb.BuilderID {
	ret := &bbpb.BuilderID{}
	if err := json.Unmarshal([]byte(s), ret); err != nil {
		panic(fmt.Sprintf("could not unmarshal builderID %q: %+v", s, err))
	}
	return ret
}

// BuildBucketAlerts returns alertable build failures generated from the given buildbucket builder.
// Invariants:
// - If the latest build succeeded, the list returned is empty for that builder.
// - Only step failures that exist in the latest build may be grouped into a range of
//   failures across builds.  Put another way: only step failures that occurred in the
//   latest build will appear anywhere in the alerts returned for that builder.
// - [TODO: diagram of some kind for the above]
func (a *Analyzer) BuildBucketAlerts(ctx context.Context, builderIDs []*bbpb.BuilderID) ([]messages.BuildFailure, error) {
	allRecentBuilds, err := a.BuildBucket.LatestBuilds(ctx, builderIDs)
	if err != nil {
		return nil, err
	}
	if len(allRecentBuilds) == 0 {
		return nil, fmt.Errorf("no recent builds from %+v", builderIDs)
	}

	// First get all of the failures that have been occurring so far for each
	// builder. This may be an empty list if there are no failures in the most
	// recent build.
	buildsByBuilderID := map[string][]*bbpb.Build{}
	for _, build := range allRecentBuilds {
		builderKey := builderIDToStr(build.Builder)
		if _, ok := buildsByBuilderID[builderKey]; !ok {
			buildsByBuilderID[builderKey] = []*bbpb.Build{}
		}
		buildsByBuilderID[builderKey] = append(buildsByBuilderID[builderKey], build)
	}

	ret := []messages.BuildFailure{}

	// TODO: Replace all *ByStep maps below with *ByReason - in the simplest case, there
	// will be only one Reason for a single step failure, and the logic will be mostly the
	// same. But for test failures there may be a really large number of Reasons per step
	// failure and for those we should do something smarter than one alert per Reason.

	// Build up a list of build ranges per builder for each alertable step.
	// The AlertedBuilder type represents a build range.
	alertedBuildersByStep := map[string][]messages.AlertedBuilder{}

	reasonsByStepName := map[string][]messages.ReasonRaw{}
	var reasonsMux sync.Mutex

	masterLocationByName := map[string]*messages.MasterLocation{}

	err = parallel.WorkPool(reasonWorkerPoolSize, func(workC chan<- func() error) {
		for builderKey, recentBuilds := range buildsByBuilderID {
			builderKey, recentBuilds := builderKey, recentBuilds

			// Assumed: recentBuilds are sorted most recent first.  TODO: Verify this is true.
			builderID := strToBuilderID(builderKey)
			latestBuild := recentBuilds[0]
			if latestBuild.Status == bbpb.Status_SUCCESS {
				continue
			}

			latestStepFailures := stepSet(
				filterNestedSteps(alertableStepFailures(latestBuild)))

			// buildsByFailingStep contains one key for each failing step in latestBuild.
			// values are slices of Build records representing continuous build runs of that failure,
			// starting at latestBuild and ending at the build where the failure first appeared.
			buildsByFailingStep := map[string][]*bbpb.Build{}

			lastPassingByStep := map[string]*bbpb.Build{}

			// Now scan through earilier builds looking for the first instances of each step failure identified.
			// Note that runs of step failures may begin at different times.
			for _, build := range recentBuilds {

				allAttemptedSteps := stepSet(build.Steps)
				alertableFailures := alertableStepFailures(build)
				for _, failure := range alertableFailures {
					failure := failure
					workC <- func() error {
						reasons := a.BuildBucketStepAnalyzers.ReasonsForFailure(ctx, failure, build)
						reasonsMux.Lock()
						defer reasonsMux.Unlock()
						reasonsByStepName[failure.Name] = reasons
						return nil
					}
				}

				// Make a stringset of the step names.
				stepFailures := stepSet(alertableFailures)
				// Now do some set calculations:
				// - step failures that exist in latestStepFailures but not in stepFailures:
				//   The previously examined build is where that step failure started. Stop looking
				//   for this step failure in subsequent iterations.
				// - step failures that exist in latestStepFailures and also in stepFailures:
				//   Include this build in the run of builders for each of these failures.
				terminatingFailures := latestStepFailures.Difference(stepFailures)

				// Don't terminate a failure unless it actually executed in this build.
				// For example, if a test fails in build X, and in build X-1 a requisite build step
				// fails and prevents tests from running, then we haven't learned anything about
				// whether the tests are still failing. If in build X-2 the tests are still failing,
				// we want that to be part of the same run of failures that started in build X.
				terminatingFailures = terminatingFailures.Intersect(allAttemptedSteps)
				for stepName := range terminatingFailures {
					if _, ok := lastPassingByStep[stepName]; !ok {
						lastPassingByStep[stepName] = build
					}
				}

				// Remove terminatingFailures from latestStepFailures.  We don't want to keep
				// looking for them in subsequent iterations of this loop.
				latestStepFailures = latestStepFailures.Difference(terminatingFailures)

				// Any failures in this build that were failing in the last examined build
				// will continue the run.
				continuingFailures := latestStepFailures.Intersect(stepFailures)

				for stepFailure := range continuingFailures {
					// Append this build to the runs of builds failing on stepFailure.
					if _, ok := buildsByFailingStep[stepFailure]; !ok {
						buildsByFailingStep[stepFailure] = []*bbpb.Build{}
					}
					buildsByFailingStep[stepFailure] = append(buildsByFailingStep[stepFailure], build)
				}
			}

			for stepName, builds := range buildsByFailingStep {
				// check ret first to see if there's already a build failure for this step
				// on some other builder. If so, just append this builder to it.
				firstFailure, latestFailure := builds[len(builds)-1], builds[0]
				if _, ok := alertedBuildersByStep[stepName]; !ok {
					alertedBuildersByStep[stepName] = []messages.AlertedBuilder{}
				}

				alertedBuilder := messages.AlertedBuilder{
					Project: builderID.Project,
					Bucket:  builderID.Bucket,
					Name:    builderID.Builder,
					URL:     fmt.Sprintf("https://ci.chromium.org/p/%s/builders/%s/%s", builderID.Project, builderID.Bucket, builderID.Builder),
					// TODO: add more buildbucket specifics to the AlertedBuilder type.
					FirstFailure:  int64(firstFailure.Number),
					LatestFailure: int64(latestFailure.Number),
					StartTime:     messages.TimeToEpochTime(time.Unix(firstFailure.StartTime.GetSeconds(), int64(firstFailure.StartTime.GetNanos()))),
				}

				master, _, err := masterAndBuilderFromInputProperties(latestFailure)
				if err != nil {
					logging.Errorf(ctx, "couldn't get master name: %v", err)
				} else {
					alertedBuilder.Master = master.Name()
					masterLocationByName[master.Name()] = master
				}

				if lastPassing, ok := lastPassingByStep[stepName]; ok {
					alertedBuilder.LatestPassing = int64(lastPassing.Number)
					firstFailingRev, err := commitRevFromOutputProperties(firstFailure)
					if err != nil {
						logging.Errorf(ctx, "failed getting commit from output, trying input: %v %#v", err, firstFailure)
						// Note: commitRevFromOutProperties will fail for chromeos builds
						// because chromeos builds don't have 'got_revision or 'got_revision_cp'.
						// Equivalent information for chromeos can be fetched from the build input.
						// (There is currently no way to get commit positions for chromeos. The frontend will
						// handle substituting positions with revisions.)
						// TODO: All builds should have rev or positions extracted using the same
						// method.
						firstFailingRev, err = commitRevFromInput(firstFailure)
						if err != nil {
							logging.Errorf(ctx, "getting commit rev: %v %#v", err, firstFailure)
						}
					}
					if err == nil {
						alertedBuilder.FirstFailingRev = firstFailingRev
					}

					lastPassingRev, err := commitRevFromOutputProperties(lastPassing)
					if err != nil {
						logging.Errorf(ctx, "failed getting commit from output, trying input: %v %#v", err, lastPassing)
						lastPassingRev, err = commitRevFromInput(lastPassing)
						if err != nil {
							logging.Errorf(ctx, "getting commit rev: %v %#v", err, lastPassing)
						}
					}
					if err == nil {
						alertedBuilder.LatestPassingRev = lastPassingRev
					}
				} else {
					logging.Errorf(ctx, "couldn't find last passing run of step %s", stepName)
				}

				alertedBuildersByStep[stepName] = append(alertedBuildersByStep[stepName], alertedBuilder)
				logging.Debugf(ctx, "should merge %d failures into an alert for step: %q", len(builds), stepName)
			}
		}
	})

	if err != nil {
		logging.Errorf(ctx, "error getting build failure reasons: %v", err)
		return nil, err
	}

	// Now group up the alerted builder ranges into individual alerts, one per step.
	// Each will contain the list of builder ranges where the step has been failing.
	for stepName, alertedBuilders := range alertedBuildersByStep {
		// While we have the alertedBuilders for this alert, we should identify the
		// narrowest range of commit posistions implicated.
		var earliestRev, latestRev *messages.RevisionSummary
		for _, alertedBuilder := range alertedBuilders {
			if earliestRev == nil || alertedBuilder.LatestPassingRev != nil && alertedBuilder.LatestPassingRev.Position > earliestRev.Position {
				earliestRev = alertedBuilder.LatestPassingRev
			}
			if latestRev == nil || alertedBuilder.FirstFailingRev != nil && alertedBuilder.FirstFailingRev.Position < latestRev.Position {
				latestRev = alertedBuilder.FirstFailingRev
			}
		}

		// TODO: update commitPosFromOutputProperties to get positions for repos besides
		// chromium. There is some uncertainty that build.Output.Properties will have this
		// information in all cases for all trees, since its contents is determined by
		// whatever is in the recipes.
		regressionRanges := []*messages.RegressionRange{}
		if latestRev != nil && earliestRev != nil {
			regressionRanges = append(regressionRanges, &messages.RegressionRange{
				Repo: earliestRev.Repo,
				Positions: []string{
					fmt.Sprintf("%s@{#%d}", earliestRev.Branch, earliestRev.Position),
					fmt.Sprintf("%s@{#%d}", latestRev.Branch, latestRev.Position),
				},
				Revisions: []string{earliestRev.GitHash, latestRev.GitHash},
				Host:      earliestRev.Host,
			})
		}

		bf := messages.BuildFailure{
			StepAtFault: &messages.BuildStep{
				Step: &messages.Step{
					Name: stepName,
				},
			},
			Builders:         alertedBuilders,
			RegressionRanges: regressionRanges,
		}

		someBuilder := alertedBuilders[0]

		if someBuilder.Project == "chromeos" {
			buildAlternativeID := messages.BuildIdentifierByNumber{
				Project: someBuilder.Project,
				Bucket:  someBuilder.Bucket,
				Builder: someBuilder.Name,
				Number:  someBuilder.LatestFailure,
			}
			results, err := a.FindIt.FinditBuildbucket(ctx, &buildAlternativeID, []string{stepName})
			if err != nil {
				logging.Errorf(ctx, "error getting findit results: %v", err)
			}

			for _, result := range results {
				if result.StepName != bf.StepAtFault.Step.Name {
					continue
				}

				bf.Culprits = append(bf.Culprits, result.Culprits...)
				bf.HasFindings = len(result.Culprits) > 0
				bf.IsFinished = result.IsFinished
				bf.IsSupported = result.IsSupported

			}
		} else if someBuilder.Project == "chromium" {
			master := masterLocationByName[someBuilder.Master]
			if master != nil {
				results, err := a.FindIt.Findit(ctx, master, someBuilder.Name, someBuilder.LatestFailure, []string{stepName})
				if err != nil {
					logging.Errorf(ctx, "error getting findit results: %v", err)
				}

				for _, result := range results {
					if result.StepName != bf.StepAtFault.Step.Name {
						continue
					}

					bf.SuspectedCLs = append(bf.SuspectedCLs, result.SuspectedCLs...)
					bf.FinditStatus = result.TryJobStatus
					bf.HasFindings = result.HasFindings
					bf.IsFinished = result.IsFinished
					bf.IsSupported = result.IsSupported

					buildNumberInURL := result.FirstKnownFailedBuildNumber
					if buildNumberInURL == 0 {
						// If Findit analysis is still running, result.FirstKnownFailedBuildNumber may be empty.
						buildNumberInURL = result.BuildNumber
					}
					buildURL := fmt.Sprintf("https://ci.chromium.org/p/%s/builders/%s/%s/%d", someBuilder.Project, someBuilder.Bucket, someBuilder.Name, buildNumberInURL)
					bf.FinditURL = fmt.Sprintf("https://findit-for-me.appspot.com/waterfall/failure?url=%s", buildURL)
				}
			}
		}

		// This assumes there is one set of reasons that applies to all instances
		// of stepName failures. Obviously this isn't always true, and we should
		// do more advanced grouping for test failures within a step, once we have
		// better and more reliable test result data.
		reasons := reasonsByStepName[stepName]

		// Add tests for same step failing for different reasons.
		for _, reason := range reasons {
			bf := bf
			bf.Reason = &messages.Reason{Raw: reason}
			ret = append(ret, bf)
		}
	}

	return ret, err
}

// Only return steps which represent leaf nodes.
// See this comment for explanation of step name flattening:
// https://chromium.googlesource.com/infra/luci/luci-go/+/HEAD/buildbucket/proto/step.proto#50
func filterNestedSteps(steps []*bbpb.Step) []*bbpb.Step {
	ret := []*bbpb.Step{}
	// Assumes that nested steps always appear in order where
	// a child immediately follows its parent, if it is nested.
	for i, step := range steps {
		if i <= len(steps)-2 {
			nextStep := steps[i+1]
			if strings.HasPrefix(nextStep.Name, step.Name+"|") {
				// Skip this step since it has at least one child.
				continue
			}
		}
		ret = append(ret, step)
	}
	return ret
}

func alertableStepFailures(build *bbpb.Build) []*bbpb.Step {
	ret := []*bbpb.Step{}
	for _, buildStep := range build.Steps {
		// "Failure reason" steps always fail *in addition* to the actual failing step,
		// so just ignore them.
		if buildStep.Status != bbpb.Status_SUCCESS && buildStep.Name != "Failure reason" {
			ret = append(ret, buildStep)
		}
	}
	return ret
}

// This is a utility function to help transition from buildbot to buildbucket.
// Some APIs we depend on (logReader, testResultsClient) still expect to have
// masters passed to them. Thankfully, build input properties often include these
// values so we just try to get them from there.
func masterAndBuilderFromInputProperties(build *bbpb.Build) (*messages.MasterLocation, string, error) {
	// Whelp, we need to get some buildbucket data into test-results server, and it
	// isn't there yet. The current test-results api requires a Master, Builder and
	// BuildNumber, which aren't native to buildbucket. So we need to pull them from
	// build properties, where someone(?) has so graciously left them (for now?).
	if build.Input == nil || build.Input.Properties == nil {
		return nil, "", fmt.Errorf("build input and/or properties not set")
	}

	masterField, ok := build.Input.Properties.Fields["mastername"]
	if !ok {
		return nil, "", fmt.Errorf("mastername property not present in build input properties")
	}
	masterStr := masterField.GetStringValue()

	builderNameField, ok := build.Input.Properties.Fields["buildername"]
	if !ok {
		return nil, "", fmt.Errorf("buildername property not present in build input properties")
	}
	builderName := builderNameField.GetStringValue()

	masterURL, err := url.Parse("https://ci.chromium.org/buildbot/" + masterStr)
	if err != nil {
		return nil, "", err
	}
	master := &messages.MasterLocation{
		URL: *masterURL,
	}

	return master, builderName, nil
}

// See https://bugs.chromium.org/p/chromium/issues/detail?id=940214 in which
// BuildBucket plans to implement first-class support for gitiles commit info.
// TODO: expand this func to return a map of repo name to commit position.
// For now, it's just chromium.
func commitRevFromOutputProperties(build *bbpb.Build) (*messages.RevisionSummary, error) {
	if build.Output == nil || build.Output.Properties == nil {
		return nil, fmt.Errorf("build output and/or properties not set")
	}

	revField, ok := build.Output.Properties.Fields["got_revision"]
	if !ok {
		return nil, fmt.Errorf("couldn't find revision in build output properties")
	}

	ret := &messages.RevisionSummary{
		GitHash: revField.GetStringValue(),
		// TODO: For all cases, get Host and Repo from the build input, like
		// in commitRevFromInput. Until it is verified that build inputs
		// for chromeos and chromium can be treated the same, the following will work
		// because got_revision is only available for chromium builds. Therefore,
		// with a successful fetch of revField, we can assume for now that
		// Host and Repo are the following.
		Host: "https://chromium.googlesource.com",
		Repo: "chromium/src",
	}

	cpField, ok := build.Output.Properties.Fields["got_revision_cp"]
	if ok {
		branch, pos, err := parseBranchAndPos(cpField.GetStringValue())
		if err != nil {
			return nil, err
		}
		ret.Branch = branch
		ret.Position = pos
	}

	return ret, nil
}

func commitRevFromInput(build *bbpb.Build) (*messages.RevisionSummary, error) {
	if build.Input == nil || build.Input.GitilesCommit == nil {
		return nil, fmt.Errorf("build input and/or gitilescommit not set")
	}

	ret := &messages.RevisionSummary{
		GitHash: build.Input.GitilesCommit.Id,
		Repo:    build.Input.GitilesCommit.Project,
		Host:    build.Input.GitilesCommit.Host,
	}
	return ret, nil
}

func parseBranchAndPos(commitPos string) (string, int, error) {
	pos := -1
	parts := strings.Split(commitPos, "@")
	if len(parts) != 2 {
		return "", -1, fmt.Errorf("couldn't parse commit position string: %q", commitPos)
	}
	_, err := fmt.Sscanf(parts[1], "{#%d}", &pos)
	return parts[0], pos, err
}
