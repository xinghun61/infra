// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

// Package flakiness implements retries of failed experimental LUCI builds.
//
// It accepts PubSub messages published by buildbucket for each build
// and retries failed ones at most 2 times.
// This is what CQ does for non-experimental builds.
//
// Other packages of luci-migration app must not depend on the fact that this
// functionality is implemented in this app.
package flakiness

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"golang.org/x/net/context"

	"google.golang.org/api/googleapi"

	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/memlock"
	"github.com/luci/luci-go/common/api/buildbucket/buildbucket/v1"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
)

const retryAttemptTagKey = "luci_migration_retry_attempt"

// Build describes a single Buildbucket build in a pubsub message.
type Build struct {
	ID             string
	Bucket         string
	Status         string
	Result         string
	Tags           []string
	ParametersJSON string `json:"parameters_json"`
}

// HandleNotification retires failed experimental LUCI builds at most 2 times.
func HandleNotification(c context.Context, build *Build, bbService *buildbucket.Service) error {
	if build.Result != "FAILURE" || !strings.HasPrefix(build.Bucket, "luci.") {
		return nil
	}
	// Note that result==FAILURE builds include infra-failed builds.

	// Do at most 2 attempts.
	retryAttempt := -1
	for _, t := range build.Tags {
		if k, v := parseTag(t); k == retryAttemptTagKey {
			var err error
			retryAttempt, err = strconv.Atoi(v)
			if err != nil {
				return errors.Annotate(err).Reason("invalid tag %(tag)q").D("tag", t).Err()
			}
			if retryAttempt >= 1 {
				logging.Infof(c, "enough retries for build %s", build.ID)
				return nil
			}
			break
		}
	}

	var parameters struct {
		Properties struct {
			Category string
		}
	}
	if err := json.Unmarshal([]byte(build.ParametersJSON), &parameters); err != nil {
		return errors.Annotate(err).Reason("could not parse parameters_json: %(json)q").
			D("json", build.ParametersJSON).
			Err()
	}

	if parameters.Properties.Category != "cq_experimental" {
		return nil
	}

	// This build should be retried.

	// Lock the build via memcache.
	err := memlock.TryWithLock(c, "retry-build-"+build.ID, info.RequestID(c), func(c context.Context) error {
		return retry(c, build, retryAttempt, bbService)
	})
	if err == memlock.ErrFailedToLock {
		logging.Infof(c, "build %s is locked, letting go", build.ID)
		return nil
	}
	return err
}

func retry(c context.Context, build *Build, attempt int, bb *buildbucket.Service) error {
	logging.Infof(c, "retrying build %s", build.ID)

	newBuild := &buildbucket.ApiPutRequestMessage{
		Bucket:            build.Bucket,
		ClientOperationId: "luci-migration-retry-" + build.ID,
		ParametersJson:    build.ParametersJSON,
		Tags: []string{
			"user_agent:luci-migration",
			retryAttemptTagKey + ":" + strconv.Itoa(attempt+1),
		},
	}
	for _, t := range build.Tags {
		switch k, _ := parseTag(t); k {
		// Buildbucket has two types of tags: initial and auto-generated.
		// The auto-generated tags, such as "builder", should not be included
		// in the Put request because buildbucket server will generate upon
		// putting a build.
		// The only tag that really matters for luci-migration app is "buildset"
		// but we add "master" too to simplify potential searching.
		case "master", "buildset":
			newBuild.Tags = append(newBuild.Tags, t)
		}
	}

	res, err := bb.Put(newBuild).Context(c).Do()
	if err != nil {
		if err, ok := err.(*googleapi.Error); ok && (err.Code == http.StatusForbidden || err.Code == http.StatusNotFound) {
			// Retries won't help. Return a non-transient error.
			// The bucket should be configured first, it is OK to skip some
			// builds.
			return errors.Annotate(err).Reason("not allowed to schedule builds in bucket %(bucket)q").
				D("bucket", newBuild.Bucket).
				Err()

		}

		return errors.Annotate(err).Reason("could not retry build %(id)q").
			D("id", build.ID).
			Transient(). // Cause a retry by returning a transient error
			Err()
	}

	resJSON, err := json.MarshalIndent(res, "", "  ")
	if err != nil {
		panic(errors.Annotate(err).Reason("could not marshal JSON response back to JSON").Err())
	}
	logging.Infof(c, "retried build %s: %s", build.ID, resJSON)
	return nil
}

// parseTag parses a buildbucket tag.
func parseTag(tag string) (k, v string) {
	parts := strings.SplitN(tag, ":", 2)
	k = parts[0]
	if len(parts) > 1 {
		v = parts[1]
	}
	return
}
