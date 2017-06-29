// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"net/url"
	"strings"
	"time"

	"github.com/luci/luci-go/common/errors"
)

type queryParam struct {
	key   string
	value string
}

// parseQueryParams parses the query parameters from a URL and returns them
// as a slice of ordered queryParam.
func parseQueryParams(q string) ([]queryParam, error) {
	q = strings.TrimPrefix(q, "?")
	if q == "" {
		return nil, nil
	}

	entries := strings.Split(q, "&")
	params := make([]queryParam, len(entries))
	for i, ent := range entries {
		parts := strings.SplitN(ent, "=", 2)

		var err error
		if params[i].key, err = url.QueryUnescape(parts[0]); err != nil {
			return nil, errors.Annotate(err, "").InternalReason("failed to unescape %q", parts[0]).Err()
		}

		if len(parts) > 1 {
			if params[i].value, err = url.QueryUnescape(parts[1]); err != nil {
				return nil, errors.Annotate(err, "").InternalReason("failed to unescape %q", parts[1]).Err()
			}
		}
	}
	return params, nil
}

func timeFromMicrosecondsSinceEpoch(ms int64) time.Time {
	const secondsInAMicrosecond = int64(time.Second) / int64(time.Microsecond)
	const microsecondsInANanosecond = int64(time.Microsecond) / int64(time.Nanosecond)

	secs := ms / secondsInAMicrosecond
	ms -= (secs * secondsInAMicrosecond)
	return time.Unix(secs, ms*microsecondsInANanosecond)
}

func trimPrefix(v string, pfx string) (string, bool) {
	if strings.HasPrefix(v, pfx) {
		return v[len(pfx):], true
	}
	return v, false
}
