// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package hostinfo

import (
	"infra/cmd/skylab_swarming_worker/internal/autotest/hostinfo"
	"infra/libs/skylab/inventory"
)

// Proxy holds a DUT's hostinfo derived from inventory info and adds a
// Close method.
type Proxy struct {
	*hostinfo.HostInfo
	dut *inventory.DeviceUnderTest
}

// Close updates the original DUT with any hostinfo changes.  This
// method does nothing on subsequent calls.  This method is safe to
// call on a nil pointer.
func (p *Proxy) Close() error {
	if p == nil {
		return nil
	}
	if p.dut == nil {
		return nil
	}
	hostinfo.RevertDut(p.dut, p.HostInfo)
	p.dut = nil
	return nil
}

// FromDUT returns a DUT's hostinfo derived from its inventory info.
// The Close method must be called to update the inventory info with
// any changes.
func FromDUT(d *inventory.DeviceUnderTest) *Proxy {
	return &Proxy{
		HostInfo: hostinfo.ConvertDut(d),
		dut:      d,
	}
}
