// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package hostinfo

import (
	"fmt"
	"strings"

	"infra/cmd/skylab_swarming_worker/internal/autotest/hostinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
)

// Borrower represents borrowing BotInfo into a HostInfo.  It is used
// for returning any relevant Hostinfo changes back to the BotInfo.
type Borrower struct {
	hostInfo *hostinfo.HostInfo
	botInfo  *swarming.BotInfo
}

// BorrowBotInfo takes some info stored in the BotInfo and adds it to
// the HostInfo.  The returned Borrower should be closed to return any
// relevant HostInfo changes back to the BotInfo.
func BorrowBotInfo(hi *hostinfo.HostInfo, bi *swarming.BotInfo) *Borrower {
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
	// Used to cache away changes to RPM power outlet state.
	"outlet_changed": {},
}
