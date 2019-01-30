// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package harness

import (
	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab_swarming_worker/internal/autotest/hostinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
	"infra/libs/skylab/inventory"
)

// loadDUTName returns the Swarming bot's DUT's name.
func loadDUTName(b *swarming.Bot) (string, error) {
	ddir, err := inventory.ReadSymlink(b.Inventory.DataDir)
	if err != nil {
		return "", errors.Annotate(err, "load DUT name").Err()
	}
	lab, err := inventory.LoadLab(ddir)
	if err != nil {
		return "", errors.Annotate(err, "load DUT name").Err()
	}
	for _, d := range lab.GetDuts() {
		c := d.GetCommon()
		if c.GetId() == b.DUTID {
			return c.GetHostname(), nil
		}
	}
	return "", errors.Reason("load DUT name: no DUT").Err()
}

// loadDUTHostInfo returns the host information for the swarming bot’s assigned DUT.
func loadDUTHostInfo(b *swarming.Bot) (*hostinfo.HostInfo, error) {
	ddir, err := inventory.ReadSymlink(b.Inventory.DataDir)
	if err != nil {
		return nil, errors.Annotate(err, "load DUT host info").Err()
	}

	lab, err := inventory.LoadLab(ddir)
	if err != nil {
		return nil, errors.Annotate(err, "load DUT host info").Err()
	}
	for _, d := range lab.GetDuts() {
		c := d.GetCommon()
		if c.GetId() != b.DUTID {
			continue
		}
		hi := hostinfo.ConvertDut(d)
		return hi, nil
	}
	return nil, errors.Reason("load DUT host info: no info found for DUT %s", b.DUTID).Err()
}
