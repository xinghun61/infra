// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package infraenv

import (
	"os"
	"path/filepath"

	"github.com/luci/luci-go/common/errors"
	"google.golang.org/cloud/compute/metadata"
)

// ErrNotFound is returned if the requested credential is not found.
var ErrNotFound = errors.New("not found")

// OnGCE will return true if the current system is a Google Compute Engine
// system.
var OnGCE = metadata.OnGCE

// GetLogDogServiceAccountJSON scans the credential directories for the LogDog
// service account JSON file.
//
// If the credential could not be located on this system, ErrNotFound will be
// returned.
func GetLogDogServiceAccountJSON() (string, error) {
	return findCredentialFile(systemCredentialDirs, "service-account-luci-logdog-publisher.json")
}

func findCredentialFile(dirs []string, name string) (string, error) {
	for _, d := range dirs {
		candidate := filepath.Join(d, name)
		if _, err := os.Stat(candidate); err != nil {
			if os.IsNotExist(err) {
				continue
			}

			return "", errors.Annotate(err).Reason("failed to check [%(path)s]").D("path", candidate).Err()
		}

		return candidate, nil
	}

	return "", ErrNotFound
}
