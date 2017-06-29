// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"net/http"
	"strings"
	"time"

	"infra/experimental/appengine/buildbucket-viewer/api/settings"

	bbapi "github.com/luci/luci-go/common/api/buildbucket/buildbucket/v1"
	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry"
	"github.com/luci/luci-go/common/retry/transient"

	"golang.org/x/net/context"
	"google.golang.org/api/googleapi"
)

const (
	// Artificially cap the maximum number of results.
	maxBuildBucketResults = 500

	// The timeout for a search. We use 60s, as the maximum amount of time that
	// AppEngine will service a user request.
	buildBucketSearchTimeout = 60 * time.Second
)

func buildBucketSearch(c context.Context, svc *bbapi.Service, buckets []string, tags []string,
	canary settings.Trinary, result, failureReason string, max int) ([]*bbapi.ApiCommonBuildMessage, error) {
	if max <= 0 || max > maxBuildBucketResults {
		max = maxBuildBucketResults
	}

	c = log.SetFields(c, log.Fields{
		"buckets":       buckets,
		"tags":          tags,
		"basePath":      svc.BasePath,
		"result":        result,
		"failureReason": failureReason,
		"max":           max,
	})
	log.Debugf(c, "Issuing BuildBucket Search().")

	// Set the Context timeout. "urlfetch" will use this to determine when
	// to timeout the request.
	c, cancelFunc := context.WithTimeout(c, buildBucketSearchTimeout)
	defer cancelFunc()

	var (
		builds []*bbapi.ApiCommonBuildMessage
		curs   string
	)
	for {
		remaining := max - len(builds)
		if remaining <= 0 {
			break
		}

		req := svc.Search().
			Bucket(buckets...).
			Tag(tags...)
		if result != "" {
			req = req.Result(result)
		}
		if failureReason != "" {
			req = req.FailureReason(failureReason)
		}

		// Apply build and cursor constraints.
		req = req.MaxBuilds(int64(remaining))
		if curs != "" {
			req = req.StartCursor(curs)
		}

		switch canary {
		case settings.Trinary_YES:
			req = req.Canary(true)
		case settings.Trinary_NO:
			req = req.Canary(false)
		}

		var res *bbapi.ApiSearchResponseMessage
		err := retry.Retry(c, transient.Only(retry.Default), func() error {
			var err error
			if res, err = req.Context(c).Do(); err != nil {
				// If this is a transient error, wrap it in a transient wrapper.
				if apiErr, ok := err.(*googleapi.Error); ok {
					if apiErr.Code >= http.StatusInternalServerError {
						err = transient.Tag.Apply(err)
					}
				}
				return err
			}
			return nil
		}, func(err error, delay time.Duration) {
			log.Fields{
				log.ErrorKey: err,
				"delay":      delay,
			}.Warningf(c, "Transient error during Search(), retrying after delay.")
		})
		if err != nil {
			return nil, errors.Annotate(err, "").InternalReason("BuildBucket Search() error").Err()
		}
		if err := res.Error; err != nil {
			return nil, errors.Annotate(makeBuildBucketError(err), "").InternalReason("error during Search()").Err()
		}

		builds = append(builds, res.Builds...)

		curs = res.NextCursor
		if curs == "" {
			break
		}
	}

	log.Fields{
		"buildCount": len(builds),
	}.Debugf(c, "Successfully retrieved builds.")
	return builds, nil
}

func makeBuildBucketError(e *bbapi.ApiErrorMessage) error {
	return errors.Reason("BuildBucket error: %s", e.Message).InternalReason(e.Reason).Err()
}

func splitTag(v string) (key string, value string) {
	switch parts := strings.SplitN(v, ":", 2); len(parts) {
	case 2:
		value = parts[1]
		fallthrough

	case 1:
		key = parts[0]
	}
	return
}

func assembleTag(k, v string) string { return strings.Join([]string{k, v}, ":") }
