// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/libs/skylab/inventory"
	"testing"

	"github.com/kylelemons/godebug/pretty"
)

var (
	botDimensions1 = &fleet.BotDimensions{
		Pools:   []string{"wifi"},
		Model:   "model1",
		DutName: "name1",
	}

	botDimensions2 = &fleet.BotDimensions{
		Pools:   []string{"wifi", "LTE"},
		Model:   "model2",
		DutName: "name2",
	}

	botDimensionsDut1 = &fleet.BotDimensions{
		Pools:   []string{"DUT_POOL_CQ"},
		Model:   "model1",
		DutName: "dutCQ",
	}

	botDimensionsDut2 = &fleet.BotDimensions{
		Pools:   []string{"DUT_POOL_SUITES"},
		Model:   "model1",
		DutName: "dutSUITES",
	}

	bs = []*fleet.BotSummary{
		{
			DutId:      "chromeOS-1",
			DutState:   fleet.DutState_Ready,
			Health:     fleet.Health_Healthy,
			Dimensions: botDimensions1,
		},
		{
			DutId:      "chromeOS-2",
			DutState:   fleet.DutState_Ready,
			Health:     fleet.Health_Healthy,
			Dimensions: botDimensions1,
		},
		{
			DutId:      "chromeOS-3",
			DutState:   fleet.DutState_Ready,
			Health:     fleet.Health_Unhealthy,
			Dimensions: botDimensions2,
		},
		{
			DutId:      "chromeOS-4",
			DutState:   fleet.DutState_Ready,
			Health:     fleet.Health_Unhealthy,
			Dimensions: botDimensions2,
		},
		{
			DutId:      "chromeOS-5",
			DutState:   fleet.DutState_Ready,
			Health:     fleet.Health_Unhealthy,
			Dimensions: botDimensionsDut1,
		},
		{
			DutId:      "chromeOS-6",
			DutState:   fleet.DutState_DutStateInvalid,
			Health:     fleet.Health_Healthy,
			Dimensions: botDimensionsDut1,
		},
		{
			DutId:      "chromeOS-7",
			DutState:   fleet.DutState_Ready,
			Health:     fleet.Health_Healthy,
			Dimensions: botDimensionsDut2,
		},
	}
)

func TestCompileInventoryReport(t *testing.T) {
	t.Parallel()
	t.Skip("Sort order is non-deterministic.")
	want := inventoryReport{
		labs: []*inventoryCount{
			{
				name:  "name2",
				good:  0,
				bad:   2,
				spare: 0,
			},
			{
				name:  "dutCQ",
				good:  1,
				bad:   1,
				spare: 0,
			},
			{
				name:  "dutSUITES",
				good:  1,
				bad:   0,
				spare: 1,
			},
			{
				name:  "name1",
				good:  2,
				bad:   0,
				spare: 0,
			},
		},
		models: []*inventoryCount{
			{
				name:  "model1",
				good:  4,
				bad:   1,
				spare: 1,
			},
			{
				name:  "model2",
				good:  0,
				bad:   2,
				spare: 0,
			},
		},
	}
	got := compileInventoryReport(bs)
	if diff := pretty.Compare(got, want); diff != "" {
		t.Errorf(`%s returned diff (-got +want): %s`, "LabCount/ModelCount_test", diff)
	}
}

func TestCompileInventoryReportByDutPool(t *testing.T) {
	t.Parallel()
	want := []*modelPools{
		{
			name: "model1",
			pools: map[inventory.SchedulableLabels_DUTPool]poolStateCount{
				inventory.SchedulableLabels_DUT_POOL_CQ: {
					ready: 1,
					total: 2,
				},
				inventory.SchedulableLabels_DUT_POOL_SUITES: {
					ready: 1,
					total: 1,
				},
			},
		},
		{
			name:  "model2",
			pools: map[inventory.SchedulableLabels_DUTPool]poolStateCount{},
		},
	}
	got := compileInventoryReportByDutPool(bs)
	if diff := pretty.Compare(got, want); diff != "" {
		t.Errorf(`%s returned diff (-got +want): %s`, "DutPoolCount_test", diff)
	}
}

func TestInventoryCount_available(t *testing.T) {
	t.Parallel()
	cases := []struct {
		desc string
		ic   inventoryCount
		want int
	}{
		{
			desc: "many spares",
			ic:   inventoryCount{good: 4, bad: 5, spare: 7},
			want: 2,
		},
		{
			desc: "few spares",
			ic:   inventoryCount{good: 4, bad: 5, spare: 3},
			want: -2,
		},
		{
			desc: "no spares",
			ic:   inventoryCount{good: 4, bad: 5},
			want: 1,
		},
		{
			desc: "no spares and few DUTs",
			ic:   inventoryCount{good: 1, bad: 2},
			want: 1,
		},
	}
	for _, c := range cases {
		c := c
		t.Run(c.desc, func(t *testing.T) {
			t.Parallel()
			got := c.ic.available()
			if got != c.want {
				t.Errorf("available() = %#v; want %#v", got, c.want)
			}
		})
	}
}

func TestGetBotLabNumberOnNormalName(t *testing.T) {
	t.Parallel()
	got := getBotLabNumber("chromeos4-rack1-row-2-host3")
	want := "4"
	if got != want {
		t.Errorf(`getBotLabNumber("chromeos4-rack1-row-2-host3") = %s; want %s`, got, want)
	}
}

func TestGetBotLabNumberOnBadName(t *testing.T) {
	t.Parallel()
	got := getBotLabNumber("rack1-row-2-host3")
	want := ""
	if got != want {
		t.Errorf(`getBotLabNumber("chromeos4-rack1-row-2-host3") = %s; want %s`, got, want)
	}
}
