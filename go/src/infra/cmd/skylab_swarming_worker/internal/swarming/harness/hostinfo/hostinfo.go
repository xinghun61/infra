// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package hostinfo implements the parts of harness management
// pertaining to Autotest hostinfo.
package hostinfo

import (
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"

	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab_swarming_worker/internal/autotest/hostinfo"
	"infra/cmd/skylab_swarming_worker/internal/botinfo"
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

// Borrower represents borrowing BotInfo into a HostInfo.  It is used
// for returning any relevant Hostinfo changes back to the BotInfo.
type Borrower struct {
	hostInfo *hostinfo.HostInfo
	botInfo  *botinfo.BotInfo
}

// BorrowBotInfo takes some info stored in the BotInfo and adds it to
// the HostInfo.  The returned Borrower should be closed to return any
// relevant HostInfo changes back to the BotInfo.
func BorrowBotInfo(hi *hostinfo.HostInfo, bi *botinfo.BotInfo) *Borrower {
	for label, value := range bi.ProvisionableLabels {
		hi.Labels = append(hi.Labels, fmt.Sprintf("%s:%s", label, value))
	}
	for attribute, value := range bi.ProvisionableAttributes {
		hi.Attributes[attribute] = value
	}
	return &Borrower{
		hostInfo: hi,
		botInfo:  bi,
	}
}

// Close returns any relevant Hostinfo changes back to the BotInfo.
// Subsequent calls do nothing.  This is safe to call on a nil pointer.
func (b *Borrower) Close() error {
	if b == nil {
		return nil
	}
	if b.botInfo == nil {
		return nil
	}
	hi, bi := b.hostInfo, b.botInfo
	for _, label := range hi.Labels {
		parts := strings.SplitN(label, ":", 2)
		if len(parts) != 2 {
			continue
		}
		if _, ok := provisionableLabelKeys[parts[0]]; ok {
			bi.ProvisionableLabels[parts[0]] = parts[1]
		}
	}
	for attribute, value := range hi.Attributes {
		if _, ok := provisionableAttributeKeys[attribute]; ok {
			bi.ProvisionableAttributes[attribute] = value
		}
	}
	b.botInfo = nil
	return nil
}

var provisionableLabelKeys = map[string]struct{}{
	"cros-version": {},
}

var provisionableAttributeKeys = map[string]struct{}{
	"job_repo_url": {},
}
