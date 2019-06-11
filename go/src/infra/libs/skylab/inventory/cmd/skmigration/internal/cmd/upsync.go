// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"infra/libs/skylab/inventory"
	"infra/libs/skylab/inventory/autotest/labels"
	"infra/libs/skylab/inventory/cmd/skmigration/internal/afedb"
	"os"

	"github.com/google/uuid"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"
)

// Upsync implements the migrate subcommand.
var Upsync = &subcommands.Command{
	UsageLine: "upsync [FLAGS]...",
	ShortDesc: "upsync inventory information from AFE database",
	LongDesc: `Upsync DUTs from Autotest to Skylab inventory.

DATA_DIR should point to the top directory of a skylab_inventory data
checkout. Upsynced data is then located at ${DATA_DIR}/prod/`,
	CommandRun: func() subcommands.CommandRun {
		c := &upsyncRun{}
		c.Flags.StringVar(&c.rootDir, "root", "", "root `directory` of the inventory checkout")
		c.Flags.StringVar(&c.dbHost, "db-host", "", "Hostname of AFE database server")
		c.Flags.StringVar(&c.dbPort, "db-port", "", "Network port used by the AFE database")
		c.Flags.StringVar(&c.dbUser, "db-user", "", "AFE database user to connect as")
		c.Flags.StringVar(&c.dbPassword, "db-password", "", "Password for the AFE database user")
		return c
	},
}

type upsyncRun struct {
	subcommands.CommandRunBase
	rootDir string

	dbHost     string
	dbPort     string
	dbUser     string
	dbPassword string
}

func (c *upsyncRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(os.Stderr, "%s\n", err)
		return 1
	}
	return 0
}

func (c *upsyncRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if err := c.validateArgs(args); err != nil {
		return err
	}

	labs, err := loadAllLabsData(c.rootDir)
	if err != nil {
		return err
	}

	dbc, err := afedb.NewClient(c.dbHost, c.dbPort, c.dbUser, c.dbPassword)
	if err != nil {
		return err
	}
	duts, err := dbc.QueryDUTs()
	if err != nil {
		return err
	}

	if err := mergeDUTs(labs.AutotestProd, duts); err != nil {
		return err
	}
	return writeAutotestProdLabData(c.rootDir, labs)
}

func (c *upsyncRun) validateArgs(args []string) error {
	if c.rootDir == "" {
		return errors.New("-root is required")
	}
	if c.dbHost == "" {
		return errors.New("-db-host is required")
	}
	if c.dbPort == "" {
		return errors.New("-db-port is required")
	}
	if c.dbUser == "" {
		return errors.New("-db-user is required")
	}
	if c.dbPort == "" {
		return errors.New("-db-port is required")
	}
	if len(args) > 0 {
		return errors.Reason("unexpected positional args: %s", args).Err()
	}
	return nil
}

func mergeDUTs(lab *inventory.Lab, duts map[string]*afedb.DUT) error {
	seen := make(stringset.Set)
	nduts := make([]*inventory.DeviceUnderTest, 0, len(duts))
	for _, d := range lab.Duts {
		h := d.GetCommon().GetHostname()
		if nd, ok := duts[h]; ok {
			seen.Add(h)
			nduts = append(nduts, toSkylabInventoryWithID(nd, d.GetCommon().GetId()))
		}
	}
	for h, nd := range duts {
		if !seen.Has(h) {
			nduts = append(nduts, toSkylabInventoryWithID(nd, uuid.New().String()))
		}
	}
	lab.Duts = nduts
	return nil
}

var allowedAttributes = map[string]bool{
	"display_id":         true,
	"HWID":               true,
	"hydra_hostname":     true,
	"os_type":            true,
	"powerunit_hostname": true,
	"powerunit_outlet":   true,
	"serial_number":      true,
	"serials":            true,
	"servo_host":         true,
	"servo_port":         true,
	"servo_serial":       true,
	"servo_type":         true,
}

func toSkylabInventoryWithID(from *afedb.DUT, id string) *inventory.DeviceUnderTest {
	attrs := make([]*inventory.KeyValue, 0, len(from.Attributes))
	for k, vs := range from.Attributes {
		k := k
		if allowedAttributes[k] {
			for _, v := range vs {
				v := v
				attrs = append(attrs, &inventory.KeyValue{Key: &k, Value: &v})
			}
		}
	}
	h := from.Hostname
	return &inventory.DeviceUnderTest{
		Common: &inventory.CommonDeviceSpecs{
			Attributes: attrs,
			Hostname:   &h,
			Id:         &id,
			Labels:     labels.Revert(from.Labels.ToSlice()),
		},
	}
}
