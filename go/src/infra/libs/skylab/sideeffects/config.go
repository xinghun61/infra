// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package sideeffects implements the validation of side effects
// configuration.
package sideeffects

import (
	"fmt"
	"os"
	"strings"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/side_effects"
)

// ValidateConfig checks the presence of all required fields in
// side_effects.Config and the existence of all required files.
func ValidateConfig(c *side_effects.Config) error {
	ma := getMissingArgs(c)

	if len(ma) > 0 {
		return fmt.Errorf("Error validating side_effects.Config: no %s provided",
			strings.Join(ma, ", "))
	}

	mf := getMissingFiles(c)

	if len(mf) > 0 {
		return fmt.Errorf("Error getting the following file(s): %s",
			strings.Join(mf, ", "))
	}

	return nil
}

func getMissingArgs(c *side_effects.Config) []string {
	var r []string

	if c.Tko.GetProxySocket() == "" {
		r = append(r, "proxy socket")
	}

	if c.Tko.GetMysqlUser() == "" {
		r = append(r, "MySQL user")
	}

	if c.Tko.GetMysqlPasswordFile() == "" {
		r = append(r, "MySQL password file")
	}

	if c.GoogleStorage.GetBucket() == "" {
		r = append(r, "Google Storage bucket")
	}

	if c.GoogleStorage.GetCredentialsFile() == "" {
		r = append(r, "Google Storage credentials file")
	}

	return r
}

func getMissingFiles(c *side_effects.Config) []string {
	var r []string

	if _, err := os.Stat(c.Tko.ProxySocket); err != nil {
		r = append(r, err.Error()+" (proxy socket)")
	}

	if _, err := os.Stat(c.Tko.MysqlPasswordFile); err != nil {
		r = append(r, err.Error()+" (MySQL password file)")
	}

	if _, err := os.Stat(c.GoogleStorage.CredentialsFile); err != nil {
		r = append(r, err.Error()+" (Google Storage credentials file)")
	}

	return r
}
