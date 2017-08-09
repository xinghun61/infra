// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package infraenv

import (
	"os"
	"path/filepath"

	"cloud.google.com/go/compute/metadata"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/hardcoded/chromeinfra"
)

// ErrNotFound is returned if the requested credential is not found.
var ErrNotFound = errors.New("not found")

// OnGCE will return true if the current system is a Google Compute Engine
// system.
var OnGCE = metadata.OnGCE

// DefaultAuthOptions returns auth.Options struct prefilled with chrome-infra
// defaults (such as OAuth client ID and path to a token cache directory).
var DefaultAuthOptions = chromeinfra.DefaultAuthOptions

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

			return "", errors.Annotate(err, "failed to check [%s]", candidate).Err()
		}

		return candidate, nil
	}

	return "", ErrNotFound
}
