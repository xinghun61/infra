// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildstatus

import (
	"net/url"
	"regexp"
	"strconv"

	"go.chromium.org/luci/common/errors"
)

var miloPathRX = regexp.MustCompile(
	`/buildbot/(?P<master>[^/]+)/(?P<builder>[^/]+)/(?P<buildNum>\d+)/?`)

// ParseBuildURL obtains master, builder and build number from the build url.
func ParseBuildURL(rawURL string) (master string, builder string, buildNum int32, err error) {
	u, err := url.Parse(rawURL)
	if err != nil {
		return
	}
	m := miloPathRX.FindStringSubmatch(u.Path)
	names := miloPathRX.SubexpNames()
	if len(m) < len(names) || m == nil {
		err = errors.Reason("The path given does not match the expected format. %s", u.Path).Err()
		return
	}
	parts := map[string]string{}
	for i, name := range names {
		if i != 0 {
			parts[name] = m[i]
		}
	}
	master, hasMaster := parts["master"]
	builder, hasBuilder := parts["builder"]
	buildNumS, hasBuildNum := parts["buildNum"]
	if !(hasMaster && hasBuilder && hasBuildNum) {
		err = errors.Reason("The path given does not match the expected format. %s", u.Path).Err()
		return
	}
	buildNumI, err := strconv.Atoi(buildNumS)
	if err != nil {
		return
	}
	buildNum = int32(buildNumI)
	return
}
