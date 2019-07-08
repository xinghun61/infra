// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package inventory

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestVerifyInventoryBadFormat(t *testing.T) {
	t.Parallel()
	d, err := ioutil.TempDir("", "test")
	if err != nil {
		t.Fatalf("Error creating temporary directory: %s", err)
	}
	defer func() {
		if err = os.RemoveAll(d); err != nil {
			t.Fatal(err)
		}
	}()

	files := []string{labFilename, infraFilename}
	content := []byte("I am bad!")
	for _, filename := range files {
		t.Run(filename, func(t *testing.T) {
			if err = ioutil.WriteFile(filepath.Join(d, filename), content, 0644); err != nil {
				t.Fatalf("Error writing to inventory file %s: %s", filename, err)
			}
			if filename == labFilename {
				err = VerifyLabInventory(d)
			} else {
				err = VerifyInfraInventory(d)
			}
			if err == nil {
				t.Fatalf("Verify bad format of inventory file %s failed!", filename)
			}
		})
	}
}

func TestVerifyInventroy(t *testing.T) {
	t.Parallel()
	d, err := ioutil.TempDir("", "test")
	if err != nil {
		t.Fatalf("Error creating temporary directory: %s", err)
	}
	defer os.RemoveAll(d)

	t.Run(labFilename, func(t *testing.T) {
		id := "dut"
		host := "host"
		lab := Lab{
			Duts: []*DeviceUnderTest{
				{Common: &CommonDeviceSpecs{
					Id:       &id,
					Hostname: &host,
				}},
			},
		}

		if err := WriteLab(&lab, d); err != nil {
			t.Fatal(err)
		}

		if err := VerifyLabInventory(d); err != nil {
			t.Fatal(err)
		}
	})

	t.Run(infraFilename, func(t *testing.T) {
		host := "host"
		env := Environment_ENVIRONMENT_PROD
		status := Server_STATUS_PRIMARY
		infra := Infrastructure{
			Servers: []*Server{
				{
					Hostname:    &host,
					Environment: &env,
					Status:      &status,
				},
			},
		}

		if err := WriteInfrastructure(&infra, d); err != nil {
			t.Fatal(err)
		}

		if err := VerifyInfraInventory(d); err != nil {
			t.Fatal(err)
		}
	})
}

func TestVerifyLabInventoryUnordered(t *testing.T) {
	t.Parallel()
	d, err := ioutil.TempDir("", "test")
	if err != nil {
		t.Fatalf("Error creating temporary directory: %s", err)
	}
	defer os.RemoveAll(d)

	t.Run(labFilename, func(t *testing.T) {
		id := "dut"
		host1 := "host1"
		host2 := "host2"
		lab := Lab{
			Duts: []*DeviceUnderTest{
				{Common: &CommonDeviceSpecs{
					Id:       &id,
					Hostname: &host1,
				}},
				{Common: &CommonDeviceSpecs{
					Id:       &id,
					Hostname: &host2,
				}},
			},
		}

		labStr, err := WriteLabToString(&lab)
		if err != nil {
			t.Fatal(err)
		}
		// Change the order by replacing the name from 'host1' to 'host3'.
		labStr = strings.Replace(labStr, "host1", "host3", 1)
		if err = ioutil.WriteFile(filepath.Join(d, labFilename), []byte(labStr), 0644); err != nil {
			t.Fatalf("Error writing to inventory file %s: %s", labFilename, err)
		}
		if err = VerifyLabInventory(d); err == nil {
			t.Fatalf("Failed to verify unordered file %s!", labFilename)
		}

	})

	t.Run(infraFilename, func(t *testing.T) {
		// TODO(guocb): don't skip this test when sortInfra implemented.
		t.Skip("sortInfra has't been implemented!")

		host1 := "host1"
		host2 := "host2"
		env := Environment_ENVIRONMENT_PROD
		status := Server_STATUS_PRIMARY
		infra := Infrastructure{
			Servers: []*Server{
				{
					Hostname:    &host1,
					Environment: &env,
					Status:      &status,
				},
				{
					Hostname:    &host2,
					Environment: &env,
					Status:      &status,
				},
			},
		}

		infraStr, err := WriteInfrastructureToString(&infra)
		if err != nil {
			t.Fatal(err)
		}
		// change the order by replacing the name from 'host1' to 'host3'
		infraStr = strings.Replace(infraStr, "host1", "host3", 1)
		if err = ioutil.WriteFile(filepath.Join(d, infraFilename), []byte(infraStr), 0644); err != nil {
			t.Fatalf("Error writing to inventory file %s: %s", infraFilename, err)
		}
		if err = VerifyInfraInventory(d); err == nil {
			t.Fatalf("Failed to verify unordered file %s!", infraFilename)
		}

	})
}
