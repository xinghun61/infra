// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dockerfile

import (
	"io/ioutil"
	"os"

	"go.chromium.org/luci/common/errors"
)

// LoadAndResolve implements high-level logic of resolving tags in a Dockerfile
// using a database loaded from a Pins YAML file.
//
// 'dockefile' must point to some existing Dockerfile on disk. It will be
// loaded, its body passed through Resolve(...) function, and returned.
//
// 'pins' should either point to a Pins YAML (see Pins struct), or should be
// an empty string (in which case the Dockerfile MUST use digests only, so
// there's nothing to resolve).
func LoadAndResolve(dockerfile, pins string) ([]byte, error) {
	body, err := ioutil.ReadFile(dockerfile)
	if err != nil {
		return nil, errors.Annotate(err, "failed to read Dockerfile").Err()
	}

	var p *Pins
	if pins != "" {
		pf, err := os.Open(pins)
		if err != nil {
			return nil, errors.Annotate(err, "failed to open pins YAML").Err()
		}
		defer pf.Close()
		p, err = ReadPins(pf)
		if err != nil {
			return nil, errors.Annotate(err, "failed to load pins YAML from %q", pins).Err()
		}
	} else {
		p = &Pins{} // empty DB, rejects all tags
	}

	if body, err = Resolve(body, p.Resolver()); err != nil {
		return nil, errors.Annotate(err, "failed to resolve tags in %q", dockerfile).Err()
	}
	return body, nil
}
