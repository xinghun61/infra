// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package resultsdir implements Autotest results directory creation
// and sealing.
package resultsdir

import (
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"time"

	"go.chromium.org/luci/common/errors"
)

// Closer is used to seal the results directory.
type Closer struct {
	path string
}

// Close seals the results directory.  This is safe to call multiple
// times.  This is safe to call on a nil pointer.
func (c *Closer) Close() error {
	if c == nil {
		return nil
	}
	if c.path == "" {
		return nil
	}
	if err := sealResultsDir(c.path); err != nil {
		return err
	}
	c.path = ""
	return nil
}

// Open creates the results directory and returns a closer for sealing
// the results directory.
func Open(path string) (*Closer, error) {
	if err := os.MkdirAll(path, 0755); err != nil {
		return nil, errors.Annotate(err, "open results dir %s", path).Err()
	}
	return &Closer{path: path}, nil
}

const gsOffloaderMarker = ".ready_for_offload"

// sealResultsDir drops a special timestamp file in the results
// directory notifying gs_offloader to offload the directory. The
// results directory should not be touched once sealed.  This should
// not be called on an already sealed results directory.
func sealResultsDir(d string) error {
	ts := []byte(fmt.Sprintf("%d", time.Now().Unix()))
	tsfile := filepath.Join(d, gsOffloaderMarker)
	if err := ioutil.WriteFile(tsfile, ts, 0666); err != nil {
		return errors.Annotate(err, "seal results dir %s", d).Err()
	}
	return nil
}
