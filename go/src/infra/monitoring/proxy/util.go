// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"time"

	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry"
	"golang.org/x/net/context"
)

// retryCall is a wrapper around the retry library that logs information about
// the retry attempts.
func retryCall(ctx context.Context, title string, f func() error) error {
	log.Debugf(ctx, "Executing retriable call %s.", title)
	err := retry.Retry(ctx, func() error {
		return f()
	}, func(err error, delay time.Duration) {
		log.Fields{
			log.ErrorKey: err,
			"delay":      delay,
		}.Warningf(ctx, "Transient error encountered during %s; retrying.", title)
	})
	if err != nil {
		log.Errorf(log.SetError(ctx, err), "Failed to %s.", title)
		return err
	}
	return nil
}

// exponentialBackoff is a retry.Factory which returns a retry.Iterator that
// implements exponential backoff.
//
// It's used for all external service calls.
func exponentialBackoff(context.Context) retry.Iterator {
	return &retry.ExponentialBackoff{
		Limited: retry.Limited{
			Delay:   200 * time.Millisecond,
			Retries: 5,
		},
		Multiplier: 3,
	}
}
