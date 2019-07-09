// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package inventory

import (
	"fmt"
	"io/ioutil"
	"path/filepath"

	"github.com/pmezard/go-difflib/difflib"

	"go.chromium.org/luci/common/errors"
)

func checkEqual(got, want string) string {
	diff := difflib.UnifiedDiff{
		A:        difflib.SplitLines(got),
		B:        difflib.SplitLines(want),
		FromFile: "What we got from inventory file",
		ToFile:   "What we want",
		Context:  3,
	}
	diffText, _ := difflib.GetUnifiedDiffString(diff)
	return diffText
}

func readInventoryFile(dataDir, filename string) (string, error) {
	fullPathName := filepath.Join(dataDir, filename)
	b, err := ioutil.ReadFile(fullPathName)
	if err != nil {
		return "", errors.Annotate(err, "load inventory %s", fullPathName).Err()
	}
	return string(b), nil
}

// verifyLabInventoryLoadAndOrder verifies the lab inventory by:
// 1. It loads and unmarshals the file to check errors.
// 2. It writes the content as string and compare it with the original file
// content. If the original file is in order, they should be same.
func verifyLabInventoryLoadAndOrder(dataDir string) error {
	labStrGot, err := readInventoryFile(dataDir, labFilename)
	if err != nil {
		return err
	}
	lab := Lab{}
	if err = LoadLabFromString(labStrGot, &lab); err != nil {
		return errors.Annotate(err, "load lab inventory %s", dataDir).Err()
	}
	labStr, err := WriteLabToString(&lab)
	if err != nil {
		return err
	}

	if diffText := checkEqual(labStrGot, labStr); diffText != "" {
		return fmt.Errorf("%s is not in order:\n\n%s", labFilename, diffText)
	}
	return nil
}

// verifyInfraInventoryLoadAndOrder verifies the infra inventory by:
// 1. It loads and unmarshals the file to check errors.
// 2. It writes the content as string and compare it with the original file
// content. If the original file is in order, they should be same.
func verifyInfraInventoryLoadAndOrder(dataDir string) error {
	infraStrGot, err := readInventoryFile(dataDir, infraFilename)
	if err != nil {
		return err
	}
	infrastructure := Infrastructure{}
	if err = LoadInfrastructureFromString(infraStrGot, &infrastructure); err != nil {
		return errors.Annotate(err, "load infrastructure inventory %s", dataDir).Err()
	}
	infraStr, err := WriteInfrastructureToString(&infrastructure)
	if err != nil {
		return err
	}
	if diffText := checkEqual(infraStrGot, infraStr); diffText != "" {
		return fmt.Errorf("%s is not in order:\n\n%s", infraFilename, diffText)
	}
	return nil
}

// VerifyLabInventory calls sub functions to verify lab inventory file, i.e.
// lab.textpb.
func VerifyLabInventory(dataDir string) error {
	return verifyLabInventoryLoadAndOrder(dataDir)
}

// VerifyInfraInventory calls sub functions to verify infra inventory file,
// i.e.  server_db.textpb.
func VerifyInfraInventory(dataDir string) error {
	return verifyInfraInventoryLoadAndOrder(dataDir)
}
