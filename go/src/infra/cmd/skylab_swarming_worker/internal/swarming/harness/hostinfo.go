// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package harness

import (
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/pkg/errors"

	"infra/cmd/skylab_swarming_worker/internal/autotest"
	"infra/cmd/skylab_swarming_worker/internal/autotest/atutil"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
	"infra/cmd/skylab_swarming_worker/internal/swarming/botcache"
)

// prepareHostInfo prepopulates the results directory with the host
// info stores required for autoserv. It returns the path to host info file created.
func prepareHostInfo(b *swarming.Bot, resultsDir string) (string, error) {
	hi, err := b.DUTHostInfo()
	if err != nil {
		return "", err
	}
	bi := b.BotInfo
	for label, value := range bi.ProvisionableLabels {
		hi.Labels = append(hi.Labels, fmt.Sprintf("%s:%s", label, value))
	}
	for attribute, value := range bi.ProvisionableAttributes {
		hi.Attributes[attribute] = value
	}
	return dumpHostInfo(b.DUTName(), resultsDir, hi)
}

// dumpHostInfo dumps the given HostInfo object to a file expected by autoserv.
// It returns the path to the created file.
func dumpHostInfo(dutName string, resultsDir string, hi *autotest.HostInfo) (string, error) {
	blob, err := autotest.MarshalHostInfo(hi)
	if err != nil {
		msg := fmt.Sprintf("failed to marshal HostInfo for %s", dutName)
		return "", errors.Wrap(err, msg)
	}
	storeDir := filepath.Join(resultsDir, atutil.HostInfoSubDir)
	if err := os.Mkdir(storeDir, 0755); err != nil {
		return "", err
	}
	storeFile := filepath.Join(storeDir, fmt.Sprintf("%s.store", dutName))
	if err := ioutil.WriteFile(storeFile, blob, 0644); err != nil {
		return "", fmt.Errorf("Failed to write HostInfo at %s: %s", storeFile, err)
	}
	log.Printf("Wrote HostInfo at %s", storeFile)
	return storeFile, nil
}

// updateBotInfoFromHostInfo reads in update host information from the concluded task and
// updates the bot dimensions with provisioned labels.
func updateBotInfoFromHostInfo(hiPath string, bi *botcache.BotInfo) error {
	blob, err := ioutil.ReadFile(hiPath)
	if err != nil {
		return errors.Wrap(err, "failed to read host info from results")
	}
	hi, err := autotest.UnmarshalHostInfo(blob)
	if err != nil {
		return errors.Wrap(err, "failed to unmarshal host info from results")
	}
	for _, label := range hi.Labels {
		updateProvisionableDimension(label, bi)
	}
	for attribute, value := range hi.Attributes {
		updateProvisionableAttributes(attribute, value, bi)
	}
	return nil
}

var provisionableLabelKeys = map[string]struct{}{
	"cros-version": {},
	// TODO(pprabhu) Remove. This is not really a provisionable label.
	// Only here for development purposes while cros-version is being added properly
	// to autoserv.
	"storage": {},
}

func updateProvisionableDimension(label string, bi *botcache.BotInfo) {
	parts := strings.SplitN(label, ":", 2)
	if len(parts) == 2 {
		if _, ok := provisionableLabelKeys[parts[0]]; ok {
			bi.ProvisionableLabels[parts[0]] = parts[1]
		}
	}
}

var provisionableAttributeKeys = map[string]struct{}{
	"job_repo_url": {},
}

func updateProvisionableAttributes(attribute string, value string, bi *botcache.BotInfo) {
	if _, ok := provisionableAttributeKeys[attribute]; ok {
		bi.ProvisionableAttributes[attribute] = value
	}
}
