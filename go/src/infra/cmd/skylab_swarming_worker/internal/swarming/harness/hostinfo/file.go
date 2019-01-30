// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package hostinfo

import (
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"

	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab_swarming_worker/internal/autotest/hostinfo"
)

// File represents a hostinfo file exposed for Autotest to use.
type File struct {
	hostInfo *hostinfo.HostInfo
	path     string
}

// hostInfoSubDir is the filename of the directory for storing host info.
const hostInfoSubDir = "host_info_store"

// Expose exposes the HostInfo as a file for Autotest to use.
func Expose(hi *hostinfo.HostInfo, resultsDir string, dutName string) (*File, error) {
	blob, err := hostinfo.Marshal(hi)
	if err != nil {
		return nil, errors.Annotate(err, "expose hostinfo").Err()
	}
	storeDir := filepath.Join(resultsDir, hostInfoSubDir)
	if err := os.Mkdir(storeDir, 0755); err != nil {
		return nil, errors.Annotate(err, "expose hostinfo").Err()
	}
	storeFile := filepath.Join(storeDir, fmt.Sprintf("%s.store", dutName))
	if err := ioutil.WriteFile(storeFile, blob, 0644); err != nil {
		return nil, errors.Annotate(err, "expose hostinfo").Err()
	}
	return &File{
		hostInfo: hi,
		path:     storeFile,
	}, nil
}

// Close marks that Autotest is finished using the exposed HostInfo
// file and loads any changes back into the original HostInfo.
// Subsequent calls do nothing.  This is safe to call on a nil pointer.
func (f *File) Close() error {
	if f == nil {
		return nil
	}
	if f.path == "" {
		return nil
	}
	blob, err := ioutil.ReadFile(f.path)
	if err != nil {
		return errors.Annotate(err, "close exposed hostinfo").Err()
	}
	hi, err := hostinfo.Unmarshal(blob)
	if err != nil {
		return errors.Annotate(err, "close exposed hostinfo").Err()
	}
	f.path = ""
	*f.hostInfo = *hi
	return nil
}
