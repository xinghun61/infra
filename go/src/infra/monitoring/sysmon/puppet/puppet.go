// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package puppet

import (
	"io/ioutil"
	"time"

	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"golang.org/x/net/context"
	"gopkg.in/yaml.v2"
)

var (
	configVersion = metric.NewInt("puppet/version/config",
		"The version of the puppet configuration.  By default this is the time that the configuration was parsed",
		nil)
	puppetVersion = metric.NewString("puppet/version/puppet",
		"Version of puppet client installed.",
		nil)
	resources = metric.NewInt("puppet/resources",
		"Number of resources known by the puppet client in its last run",
		nil,
		field.String("action"))
	times = metric.NewFloat("puppet/times",
		"Time taken to perform various parts of the last puppet run",
		nil,
		field.String("step"))
	events = metric.NewInt("puppet/events",
		"Number of changes the puppet client made to the system in its last run, by success or failure",
		nil,
		field.String("result"))
	age = metric.NewFloat("puppet/age",
		"Time since last run",
		nil)
)

type lastRunData struct {
	Version struct {
		Config int64
		Puppet string
	}
	Resources map[string]int64
	Time      map[string]float64
	Changes   map[string]int64
	Events    map[string]int64
}

// Register adds tsmon callbacks to set puppet metrics.
func Register() {
	tsmon.RegisterCallback(func(c context.Context) {
		path, err := lastRunFile()
		if err != nil {
			logging.Warningf(c, "Failed to get puppet last_run_summary.yaml path: %v", err)
			return
		}

		if err := update(c, path); err != nil {
			logging.Warningf(c, "Failed to update puppet metrics: %v", err)
		}
	})
}

func update(c context.Context, path string) error {
	raw, err := ioutil.ReadFile(path)
	if err != nil {
		return err
	}

	var data lastRunData
	if err := yaml.Unmarshal(raw, &data); err != nil {
		return err
	}

	configVersion.Set(c, data.Version.Config)
	puppetVersion.Set(c, data.Version.Puppet)

	for k, v := range data.Resources {
		resources.Set(c, v, k)
	}
	for k, v := range data.Events {
		if k != "total" {
			events.Set(c, v, k)
		}
	}
	for k, v := range data.Time {
		if k == "last_run" {
			age.Set(c, float64(clock.Now(c).Sub(time.Unix(int64(v), 0))/time.Second))
		} else if k != "total" {
			times.Set(c, v, k)
		}
	}

	return nil
}
