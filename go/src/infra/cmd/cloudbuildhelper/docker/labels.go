// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package docker

import (
	"fmt"
	"sort"
	"time"
)

// Labels is a schema for docker image labels we set.
//
// See https://github.com/opencontainers/image-spec/blob/master/annotations.md
// for org.opencontainers.image.* labels.
type Labels struct {
	Created      time.Time // org.opencontainers.image.created=<RFC3339 timestamp>
	BuildTool    string    // org.chromium.build.tool="cloudbuildhelper v1.2.3"
	BuildMode    string    // org.chromium.build.mode="local" (or "cloudbuild")
	Inputs       string    // org.chromium.build.inputs=<SHA256 of context tarball>
	BuildID      string    // org.chromium.build.id="...
	CanonicalTag string    // org.chromium.build.canonical=...

	Extra map[string]string // whatever was supplied via -label CLI flag
}

// Sorted returns a sorted list of k=v pairs with labels.
func (l *Labels) Sorted() []string {
	all := make(map[string]string, len(l.Extra)+4)
	for k, v := range l.Extra {
		all[k] = v
	}

	if !l.Created.IsZero() {
		all["org.opencontainers.image.created"] = l.Created.Format(time.RFC3339)
	}
	if l.BuildTool != "" {
		all["org.chromium.build.tool"] = l.BuildTool
	}
	if l.BuildMode != "" {
		all["org.chromium.build.mode"] = l.BuildMode
	}
	if l.Inputs != "" {
		all["org.chromium.build.inputs"] = l.Inputs
	}
	if l.BuildID != "" {
		all["org.chromium.build.id"] = l.BuildID
	}
	if l.CanonicalTag != "" {
		all["org.chromium.build.canonical"] = l.CanonicalTag
	}

	str := make([]string, 0, len(all))
	for k, v := range all {
		str = append(str, fmt.Sprintf("%s=%s", k, v))
	}
	sort.Strings(str)
	return str
}

// AsBuildArgs returns ["--label", "k=v", "--label", "k=v", ...].
func (l *Labels) AsBuildArgs() []string {
	all := l.Sorted()
	args := make([]string, 0, 2*len(all))
	for _, kv := range all {
		args = append(args, "--label", kv)
	}
	return args
}
