// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package botcache provides support for caching information on swarming bots.
*/
package botcache

import (
	"encoding/json"
)

// BotInfo contains persistent bot information that is cached on the
// Skylab drone.
type BotInfo struct {
	HostState               HostState               `json:"state"`
	ProvisionableLabels     ProvisionableLabels     `json:"provisionable_labels"`
	ProvisionableAttributes ProvisionableAttributes `json:"provisionable_attributes"`
}

// HostState is an enum for host state.
type HostState string

// ProvisionableLabels stores provisionable labels for a bot and host.
type ProvisionableLabels map[string]string

// ProvisionableAttributes stores provisionable attributes for a bot and host.
type ProvisionableAttributes map[string]string

// Valid values for HostState.
const (
	HostReady        HostState = "ready"
	HostNeedsRepair  HostState = "needs_repair"
	HostNeedsCleanup HostState = "needs_cleanup"
	HostNeedsReset   HostState = "needs_reset"
	HostRepairFailed HostState = "repair_failed"

	// Deprecated
	HostRunning HostState = "running"
)

// Marshal returns the encoding of the BotInfo.
func Marshal(bi *BotInfo) ([]byte, error) {
	return json.Marshal(bi)
}

// Unmarshal decodes BotInfo from the encoded data.
func Unmarshal(data []byte, bi *BotInfo) error {
	if err := json.Unmarshal(data, bi); err != nil {
		return err
	}
	if bi.ProvisionableLabels == nil {
		bi.ProvisionableLabels = make(map[string]string)
	}
	if bi.ProvisionableAttributes == nil {
		bi.ProvisionableAttributes = make(map[string]string)
	}
	return nil
}
