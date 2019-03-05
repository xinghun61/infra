// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"errors"
	"fmt"

	"github.com/maruel/subcommands"

	"infra/libs/skylab/inventory"
)

// ImportServoAttributes implements the import-servo-attributes subcommand.
var ImportServoAttributes = &subcommands.Command{
	UsageLine: "import-servo-attributes -root DATA_DIR",
	ShortDesc: "import servo attributes from Autotest for migrated DUTs",
	LongDesc: `Import servo attributes from Autotest for migrated DUTs.

Servo attributes are often manually updated as part of the 'deploy repair'
process. These are not automatically synced into Skylab.
Use this tool to sync the attributes before deleting the DUTs from Autotest.

DATA_DIR should point to the top directory of a skylab_inventory data
checkout. Skylab data is then located at ${DATA_DIR}/data/skylab`,
	CommandRun: func() subcommands.CommandRun {
		c := &importServoAttributesRun{}
		c.Flags.StringVar(&c.rootDir, "root", "", "root `directory` of the inventory checkout")
		return c
	},
}

type importServoAttributesRun struct {
	subcommands.CommandRunBase
	rootDir string
}

func (c *importServoAttributesRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "import-servo-attributes: %s\n", err)
		return 1
	}
	return 0
}

func (c *importServoAttributesRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if c.rootDir == "" {
		return errors.New("-root is required")
	}

	labs, err := loadAllLabsData(c.rootDir)
	if err != nil {
		return err
	}
	importServoAttributes(labs.Skylab, labs.AutotestProd)
	importServoAttributes(labs.Skylab, labs.AutotestDev)
	return writeSkylabLabData(c.rootDir, labs)
}

var attributeKeyWhitelist = map[string]bool{
	"servo_host":   true,
	"servo_port":   true,
	"servo_serial": true,
}

func importServoAttributes(target *inventory.Lab, source *inventory.Lab) {
	duts := dutsByHostname(source)
	for _, tDUT := range target.GetDuts() {
		sDUT, ok := duts[tDUT.GetCommon().GetHostname()]
		if !ok {
			continue
		}

		sAttributes := toAttributesMap(sDUT.GetCommon().GetAttributes())
		tAttributes := toAttributesMap(tDUT.GetCommon().GetAttributes())
		for k := range attributeKeyWhitelist {
			if v, ok := sAttributes[k]; ok {
				tAttributes[k] = v
			}
		}
		mergeAttributes(tDUT, tAttributes)
	}
}

func dutsByHostname(lab *inventory.Lab) map[string]*inventory.DeviceUnderTest {
	m := make(map[string]*inventory.DeviceUnderTest)
	for _, d := range lab.Duts {
		m[d.GetCommon().GetHostname()] = d
	}
	return m
}

func toAttributesMap(kvs []*inventory.KeyValue) map[string]string {
	m := make(map[string]string)
	for _, kv := range kvs {
		m[*kv.Key] = *kv.Value
	}
	return m
}

// mergeAttributes updates the attributes in tDUT from those in attrs.
//
// For attributes that already exist in tDUT, their value is updated in-place.
// New attributes are appended to the end of the list.
func mergeAttributes(tDUT *inventory.DeviceUnderTest, attrs map[string]string) {
	if len(attrs) == 0 {
		return
	}

	seen := make(map[string]bool)
	c := tDUT.GetCommon()
	for _, kv := range c.GetAttributes() {
		if v, ok := attrs[*kv.Key]; ok {
			kv.Value = &v
			seen[*kv.Key] = true
		}
	}
	for k, v := range attrs {
		if seen[k] {
			continue
		}
		c.Attributes = append(c.Attributes, &inventory.KeyValue{
			Key:   &k,
			Value: &v,
		})
	}
}
