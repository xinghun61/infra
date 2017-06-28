// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

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

	"golang.org/x/net/context"

	"google.golang.org/api/googleapi"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/memcache"
	"github.com/luci/luci-go/common/api/buildbucket/buildbucket/v1"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry/transient"

	"infra/appengine/luci-migration/bbutil"
	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"
)

const (
	attemptTagKey         = "luci_migration_attempt"
	buildbotBuildIDTagKey = "luci_migration_buildbot_build_id"
)

// HandleNotification retries builds on LUCI.
func HandleNotification(c context.Context, build *buildbucket.ApiCommonBuildMessage, bbService *buildbucket.Service) error {
	switch {
	case build.Status == bbutil.StatusCompleted && strings.HasPrefix(build.Bucket, "master."):
		return handleCompletedBuildbotBuild(c, build, bbService)

	case build.Result == bbutil.ResultFailure && strings.HasPrefix(build.Bucket, "luci."):
		// Note that result==FAILURE builds include infra-failed builds.
		return handleFailedLUCIBuild(c, build, bbService)

	default:
		return nil
	}
}

// handleCompletedBuildbot schedules a Buildbot build on LUCI if the build
// is for a builder that we track. Honors builder's experiment percentage.
func handleCompletedBuildbotBuild(c context.Context, build *buildbucket.ApiCommonBuildMessage, bbService *buildbucket.Service) error {
	buildSet := bbutil.BuildSet(build)
	if buildSet == "" {
		return nil
	}

	// Is it a builder that we care about?
	builder := &storage.Builder{ID: storage.BuilderID{
		Master:  strings.TrimPrefix(build.Bucket, "master."),
		Builder: bbutil.Builder(build),
	}}
	switch err := datastore.Get(c, builder); {
	case err == datastore.ErrNoSuchEntity:
		return nil // no, we don't care about it
	case err != nil:
		return errors.Annotate(err).Reason("could not read builder %(id)s").D("id", &builder.ID).Err()
	}
	if builder.SchedulingType != config.SchedulingType_TRYJOBS {
		// we don't support non-tryjob yet
		return nil
	}

	// Should we experiment with this CL?
	if !shouldExperiment(buildSet, builder.ExperimentPercentage) {
		return nil
	}

	// This build should be scheduled on LUCI.

	// Retrieve "got_revision"
	revision, err := gotRevision(build)
	switch {
	case err != nil:
		return err
	case revision == "":
		return errors.Reason("could not find got_revision in build %(id)d").D("id", build.Id).Err()
	}

	// Prepare new build request.

	newBuild := &buildbucket.ApiPutRequestMessage{
		Bucket:            builder.LUCIBuildbucketBucket,
		ClientOperationId: "luci-migration-retry-" + strconv.FormatInt(build.Id, 10),
		Tags: []string{
			bbutil.FormatTag(buildbotBuildIDTagKey, strconv.FormatInt(build.Id, 10)),
			bbutil.FormatTag(attemptTagKey, "0"),
			bbutil.FormatTag(bbutil.TagBuildSet, buildSet),
		},
	}

	var parameters map[string]interface{}
	if err := json.Unmarshal([]byte(build.ParametersJson), &parameters); err != nil {
		return err
	}
	parameters["builder_name"] = builder.LUCIBuildbucketBuilder

	// Set got_revision
	var props map[string]interface{} // a pointer to "properties" in parameters
	if propsRaw, ok := parameters["properties"]; ok {
		props, ok = propsRaw.(map[string]interface{})
		if !ok {
			return errors.New("properties is not a JSON object")
		}
	} else {
		props = map[string]interface{}{}
		parameters["properties"] = props
	}
	props["revision"] = revision

	// Mark the build as experimental, so it does not confuse users of Rietveld and Gerrit.
	props["category"] = "cq_experimental"

	if marshalled, err := json.Marshal(parameters); err != nil {
		return err
	} else {
		newBuild.ParametersJson = string(marshalled)
	}

	return withLock(c, build.Id, func() error {
		logging.Infof(
			c,
			"scheduling Buildbot build %d on LUCI for builder %q and buildset %q",
			build.Id, &builder.ID, buildSet)
		return schedule(c, newBuild, bbService)
	})
}

func handleFailedLUCIBuild(c context.Context, build *buildbucket.ApiCommonBuildMessage, bbService *buildbucket.Service) error {
	buildSet := ""
	attempt := -1
	buildbotBuildID := ""
	for _, t := range build.Tags {
		var err error
		switch k, v := bbutil.ParseTag(t); k {
		case attemptTagKey:
			attempt, err = strconv.Atoi(v)
		case buildbotBuildIDTagKey:
			buildbotBuildID = v
		case bbutil.TagBuildSet:
			buildSet = v
		}
		if err != nil {
			return errors.Annotate(err).Reason("invalid tag %(tag)q").D("tag", t).Err()
		}
	}
	switch {
	case attempt < 0 || buildSet == "":
		return nil // we don't recognize this build

	// Do at most 3 attempts.
	case attempt >= 2:
		logging.Infof(c, "enough retries for build %s", buildbotBuildID)
		return nil
	}

	// Before retrying the build, see if there is a newer one already created.
	// It may happen if a new Buildbot build completed.
	req := bbService.Search()
	req.Bucket(build.Bucket)
	req.Tag(
		bbutil.FormatTag(bbutil.TagBuildSet, buildSet),
		bbutil.FormatTag("builder", bbutil.Builder(build)),
	)
	switch newerBuilds, err := bbutil.SearchAll(c, req, bbutil.ParseTimestamp(build.CreatedTs+1)); {
	case err != nil:
		return errors.Annotate(err).Reason("failed to search newer builds").Err()
	case len(newerBuilds) > 0:
		logging.Infof(c, "not retrying because build %d is newer", newerBuilds[0].Id)
		return nil
	}

	newBuild := &buildbucket.ApiPutRequestMessage{
		Bucket:            build.Bucket,
		ClientOperationId: "luci-migration-retry-" + strconv.FormatInt(build.Id, 10),
		ParametersJson:    build.ParametersJson,
		Tags: []string{
			bbutil.FormatTag(buildbotBuildIDTagKey, buildbotBuildID),
			bbutil.FormatTag(attemptTagKey, strconv.Itoa(attempt+1)),
			bbutil.FormatTag(bbutil.TagBuildSet, buildSet),
		},
	}

	return withLock(c, build.Id, func() error {
		logging.Infof(c, "retrying LUCI build %d", build.Id)
		return schedule(c, newBuild, bbService)
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
		return errors.Annotate(err).Reason("could not lock on build %(id)d").D("id", buildID).Err()
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
func schedule(c context.Context, req *buildbucket.ApiPutRequestMessage, service *buildbucket.Service) error {
	req.Tags = append(req.Tags, "user_agent:luci-migration")
	res, err := service.Put(req).Context(c).Do()
	if err == nil && res.Error != nil {
		err = errors.New(res.Error.Message)
	}
	if err != nil {
		if err, ok := err.(*googleapi.Error); ok && (err.Code == http.StatusForbidden || err.Code == http.StatusNotFound) {
			// Retries won't help. Return a non-transient error.
			// The bucket should be configured first, it is OK to skip some
			// builds.
			return errors.Annotate(err).Reason("not allowed to schedule builds in bucket %(bucket)q").
				D("bucket", req.Bucket).
				Err()
		}

		return errors.Annotate(err).Reason("could not schedule a build").
			Tag(transient.Tag). // Cause a retry by returning a transient error
			Err()
	}

	resJSON, err := json.MarshalIndent(res, "", "  ")
	if err != nil {
		panic(errors.Annotate(err).Reason("could not marshal JSON response back to JSON").Err())
	}
	logging.Infof(c, "scheduled new build: %s", resJSON)
	return nil
}

// shouldExperiment deterministically returns true if experiments must be done
// for the buildset.
func shouldExperiment(buildSet string, percentage int) bool {
	switch {
	case percentage <= 0:
		return false
	case percentage >= 100:
		return true
	default:
		aByte := sha256.Sum256([]byte(buildSet))[0]
		return int(aByte)*100 <= percentage*255
	}
}

// gotRevision returns "got_revision" property value.
func gotRevision(build *buildbucket.ApiCommonBuildMessage) (string, error) {
	var resultDetails struct {
		Properties struct {
			GotRevision string `json:"got_revision"`
		}
	}
	if err := json.Unmarshal([]byte(build.ResultDetailsJson), &resultDetails); err != nil {
		return "", errors.Annotate(err).Reason("could not parse buildbot build result details").Err()
	}
	return resultDetails.Properties.GotRevision, nil
}
