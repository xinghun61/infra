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

// Package scheduling schedules Buildbot builds on LUCI.
//
// It accepts PubSub messages published by Buildbucket for each build.
// If it is a Buildbot build for a builder that we want to migrate,
// schedules an equivalent LUCI build, for a percentage of CLs.
// If it is a failed LUCI build, retries at most 2 times.
//
// Other packages of luci-migration app must not depend on the fact that this
// functionality is implemented in this app.
package scheduling

import (
	"crypto/sha256"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"

	"golang.org/x/net/context"

	"google.golang.org/api/googleapi"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/buildbucket/deprecated"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/buildbucket/protoutil"
	bbapi "go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry/transient"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"
)

const (
	attemptTagKey         = "luci_migration_attempt"
	buildbotBuildIDTagKey = "luci_migration_buildbot_build_id"
)

// Build is a buildbucket Build.
type Build struct {
	ID             int64
	Bucket         string
	Builder        string
	ParametersJSON string
	CreationTime   time.Time
	Change         *buildbucketpb.GerritChange
	Status         buildbucketpb.Status
	GotRevision    string
	DryRun         interface{}

	// Luci-migration-specific info:

	Attempt         int   // migration-app's attempt. -1 if unknown.
	BuildbotBuildID int64 // buildbucket id of the original buildbot build
}

// ParseBuild parses a raw buildbucket build message to a Build.
func ParseBuild(msg *bbapi.LegacyApiCommonBuildMessage) (*Build, error) {
	tags := strpair.ParseMap(msg.Tags)
	build := &Build{
		ID:             msg.Id,
		Bucket:         msg.Bucket,
		Builder:        tags.Get(bbapi.TagBuilder),
		ParametersJSON: msg.ParametersJson,
		CreationTime:   bbapi.ParseTimestamp(msg.CreatedTs),
		Attempt:        -1,
	}

	for _, bss := range tags[bbapi.TagBuildSet] {
		build.Change, _ = protoutil.ParseBuildSet(bss).(*buildbucketpb.GerritChange)
		if build.Change != nil {
			break
		}
	}

	var err error
	if build.Status, err = deprecated.StatusToV2(msg); err != nil {
		return nil, errors.Annotate(err, "failed to parse build status").Err()
	}

	if msg.ResultDetailsJson != "" {
		var resultDetails struct {
			Properties struct {
				GotRevision string      `json:"got_revision"`
				DryRun      interface{} `json:"dry_run"`
			} `json:"properties"`
		}
		if err = json.NewDecoder(strings.NewReader(msg.ResultDetailsJson)).Decode(&resultDetails); err != nil {
			return nil, errors.Annotate(err, "failed to parse result details").Err()
		}
		build.GotRevision = resultDetails.Properties.GotRevision
		build.DryRun = resultDetails.Properties.DryRun
	}

	if attemptStr := tags.Get(attemptTagKey); attemptStr != "" {
		if build.Attempt, err = strconv.Atoi(attemptStr); err != nil {
			return nil, errors.Annotate(err, "invalid %s tag: %s", attemptTagKey, attemptStr).Err()
		}
	}

	if buildbotIDStr := tags.Get(buildbotBuildIDTagKey); buildbotIDStr != "" {
		if build.BuildbotBuildID, err = strconv.ParseInt(buildbotIDStr, 10, 64); err != nil {
			return nil, errors.Annotate(err, "invalid %s tag: %s", buildbotBuildIDTagKey, buildbotIDStr).Err()
		}
	}

	return build, nil
}

// Scheduler schedules Buildbot builds on LUCI.
type Scheduler struct {
	Buildbucket *bbapi.Service
}

// BuildCompleted handles a build completion notification.
func (h *Scheduler) BuildCompleted(c context.Context, build *Build) error {
	switch {
	case protoutil.IsEnded(build.Status) && strings.HasPrefix(build.Bucket, "master."):
		return h.buildbotBuildCompleted(c, build)

	case (build.Status == buildbucketpb.Status_FAILURE || build.Status == buildbucketpb.Status_INFRA_FAILURE) &&
		strings.HasPrefix(build.Bucket, "luci."):

		// Note that result==FAILURE builds include infra-failed builds.
		return h.luciBuildFailed(c, build)

	default:
		return nil
	}
}

// buildbotBuildCompleted schedules a Buildbot build on LUCI if the build
// is for a builder that we track. Honors builder's experiment percentage and
// build creation rate limit.
func (h *Scheduler) buildbotBuildCompleted(c context.Context, build *Build) error {
	if build.Change == nil {
		// Not a useful try build.
		return nil
	}

	// Is it a builder that we care about?
	builder := &storage.Builder{ID: storage.BuilderID{
		Master:  strings.TrimPrefix(build.Bucket, "master."),
		Builder: build.Builder,
	}}
	switch err := datastore.Get(c, builder); {
	case err == datastore.ErrNoSuchEntity:
		return nil // no, we don't care about it
	case err != nil:
		return errors.Annotate(err, "could not read builder %s", &builder.ID).Err()
	}
	if builder.SchedulingType != config.SchedulingType_TRYJOBS {
		// we don't support non-tryjob yet
		return nil
	}
	master := config.Get(c).FindMaster(builder.ID.Master)
	if master == nil {
		return errors.Reason("master %q is not configured", builder.ID.Master).Err()
	}

	// Should we experiment with this CL?
	if !shouldExperiment(build.Change, builder.ExperimentPercentage) {
		return nil
	}

	// This build should be scheduled on LUCI.
	// Prepare new build request.
	props := map[string]interface{}{
		"revision": build.GotRevision,
		// Mark the build as experimental, so it does not confuse users of Rietveld and Gerrit.
		"category": "cq_experimental",
	}
	if build.DryRun != nil {
		props["dry_run"] = build.DryRun
	}
	newParamsJSON, err := setProps(build.ParametersJSON, props)
	if err != nil {
		return err
	}
	newTags := strpair.Map{}
	newTags.Set(buildbotBuildIDTagKey, strconv.FormatInt(build.ID, 10))
	newTags.Set(attemptTagKey, "0")
	newTags.Set(bbapi.TagBuildSet, protoutil.GerritBuildSet(build.Change))
	newBuild := &bbapi.LegacyApiPutRequestMessage{
		Bucket:            master.LuciBucket,
		ClientOperationId: "luci-migration-retry-" + strconv.FormatInt(build.ID, 10),
		ParametersJson:    newParamsJSON,
		Tags:              newTags.Format(),
	}
	return withLock(c, build.ID, func() error {
		logging.Infof(
			c,
			"scheduling Buildbot build %d on LUCI for builder %q and %q",
			build.ID, &builder.ID, protoutil.GerritChangeURL(build.Change))
		return h.schedule(c, builder.ID.Builder, newBuild)
	})
}

func (h *Scheduler) luciBuildFailed(c context.Context, build *Build) error {
	switch {
	case build.Attempt < 0 || build.Change == nil || build.BuildbotBuildID == 0:
		return nil // we don't recognize this build

	// Do at most 3 attempts.
	case build.Attempt >= 2:
		logging.Infof(c, "hit max retries for build %d", build.BuildbotBuildID)
		return nil
	}

	changeBS := protoutil.GerritBuildSet(build.Change)

	// Before retrying the build, see if there is a newer one already created.
	// It may happen if a new Buildbot build completed.
	req := h.Buildbucket.Search()
	req.Context(c)
	req.Bucket(build.Bucket)
	req.CreationTsLow(bbapi.FormatTimestamp(build.CreationTime) + 1)
	req.IncludeExperimental(true)
	req.Tag(
		strpair.Format(bbapi.TagBuildSet, changeBS),
		strpair.Format(bbapi.TagBuilder, build.Builder),
	)
	switch newerBuilds, _, err := req.Fetch(1, nil); {
	case err != nil:
		return errors.Annotate(err, "failed to search newer builds").Err()
	case len(newerBuilds) > 0:
		logging.Infof(c, "not retrying because build %d is newer", newerBuilds[0].Id)
		return nil
	}

	newTags := strpair.Map{}
	newTags.Set(buildbotBuildIDTagKey, strconv.FormatInt(build.BuildbotBuildID, 10))
	newTags.Set(attemptTagKey, strconv.Itoa(build.Attempt+1))
	newTags.Set(bbapi.TagBuildSet, changeBS)
	newBuild := &bbapi.LegacyApiPutRequestMessage{
		Bucket:            build.Bucket,
		ClientOperationId: "luci-migration-retry-" + strconv.FormatInt(build.ID, 10),
		ParametersJson:    build.ParametersJSON,
		Tags:              newTags.Format(),
	}

	return withLock(c, build.ID, func() error {
		logging.Infof(c, "retrying LUCI build %d", build.ID)
		return h.schedule(c, build.Builder, newBuild)
	})
}

// withLock locks on the build id and, on success, calls f.
// Does not release the lock if f returns nil.
func withLock(c context.Context, buildID int64, f func() error) error {
	// Lock the build via memcache.
	lock := memcache.NewItem(c, "retry-build-"+strconv.FormatInt(buildID, 10))
	switch err := memcache.Add(c, lock); {
	case err == memcache.ErrNotStored:
		logging.Infof(c, "build %d is locked, letting go", buildID)
		return nil

	case err != nil:
		return errors.Annotate(err, "could not lock on build %d", buildID).Err()
	}

	unlock := true
	defer func() {
		if unlock {
			if err := memcache.Delete(c, lock.Key()); err != nil {
				// too bad. The analysis algorithm will probably ignore this patchset.
				logging.WithError(err).Errorf(c, "could not unlock build")
			}
		}
	}()

	if err := f(); err != nil {
		return err
	}

	unlock = false
	return nil
}

// schedule creates a build and logs a successful result.
func (h *Scheduler) schedule(c context.Context, builder string, req *bbapi.LegacyApiPutRequestMessage) error {
	req.Tags = append(req.Tags, "user_agent:luci-migration")
	req.Experimental = true

	res, err := h.Buildbucket.Put(req).Context(c).Do()
	transientFailure := true
	if err == nil && res.Error != nil {
		err = errors.New(res.Error.Message)
		// A LUCI builder may be not defined for a buildbot builder yet.
		// Skip such builds. When the LUCI builder is defined, builds will
		// start flowing.
		transientFailure = res.Error.Reason != "BUILDER_NOT_FOUND"
	}
	if err != nil {
		if apierr, ok := err.(*googleapi.Error); ok && (apierr.Code == http.StatusForbidden || apierr.Code == http.StatusNotFound) {
			// Retries won't help. Return a non-transient error.
			// The bucket should be configured first, it is OK to skip some
			// builds.
			transientFailure = false
		}

		ann := errors.Annotate(err, "could not schedule a build")
		if transientFailure {
			ann.Tag(transient.Tag) // Cause a retry by returning a transient error
		}
		return ann.Err()
	}

	resJSON, err := json.MarshalIndent(res, "", "  ")
	if err != nil {
		panic(errors.Annotate(err, "could not marshal JSON response back to JSON").Err())
	}
	logging.Infof(c, "scheduled new build: %s", resJSON)
	return nil
}

// shouldExperiment deterministically returns true if experiments must be done
// for the CL.
func shouldExperiment(change *buildbucketpb.GerritChange, percentage int) bool {
	switch {
	case percentage <= 0:
		return false
	case percentage >= 100:
		return true
	default:
		aByte := sha256.Sum256([]byte(protoutil.GerritBuildSet(change)))[0]
		return int(aByte)*100 <= percentage*255
	}
}

func setProps(paramsJSON string, values map[string]interface{}) (string, error) {
	var parameters map[string]interface{}
	if err := json.Unmarshal([]byte(paramsJSON), &parameters); err != nil {
		return "", err
	}

	var props map[string]interface{} // a pointer to "properties" in parameters
	if propsRaw, ok := parameters["properties"]; ok {
		props, ok = propsRaw.(map[string]interface{})
		if !ok {
			return "", errors.New("properties is not a JSON object")
		}
	} else {
		props = map[string]interface{}{}
		parameters["properties"] = props
	}

	for k, v := range values {
		props[k] = v
	}

	marshalled, err := json.Marshal(parameters)
	if err != nil {
		return "", err
	}
	return string(marshalled), nil
}
