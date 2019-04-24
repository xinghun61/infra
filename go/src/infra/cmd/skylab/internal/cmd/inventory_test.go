// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bytes"
	"reflect"
	"testing"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"

	"github.com/kylelemons/godebug/pretty"
)

func TestCompileInventoryReport(t *testing.T) {
	// TODO(ayatane): Fix these tests.  They depend on trailing
	// whitespace and really shouldn't be comparing the formatted
	// text.  Also, the sort order is non-deterministic.
	t.Skip("Sort order is non-deterministic.")
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

	tests := []struct {
		desc       string
		botSummary []*fleet.BotSummary
		showPools  bool
		want       string
	}{
		{
			desc:       "LabCount/ModelCount_test",
			botSummary: bs,
			showPools:  false,
			want: `Inventory by location
===============================================================================
Location   Avail  Good  Bad  Spare  Total  
name2      0      0     2    0      2      
dutCQ      1      1     1    0      2      
dutSUITES  1      1     0    1      1      
name1      2      2     0    0      2      

Inventory by model
===============================================================================
Model   Avail  Good  Bad  Spare  Total  
model2  0      0     2    0      2      
model1  0      4     1    1      5      
`,
		},
		{
			desc:       "DutPoolCount_test",
			botSummary: bs,
			showPools:  true,
			want: `DUT Pool Count by model
===============================================================================
Model   DUT_POOL_CQ  DUT_POOL_SUITES  
model1  1/2          1/1              
model2  0/0          0/0              
`,
		},
	}
	t.Parallel()
	for _, test := range tests {
		got := printInventoryReportToBuffer(test.botSummary, test.showPools)
		if !reflect.DeepEqual(got, test.want) {
			t.Errorf(`%s returned diff (-got +want): %s`, test.desc, pretty.Compare(got, test.want))
		}
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

func printInventoryReportToBuffer(bs []*fleet.BotSummary, showPools bool) string {
	w := &bytes.Buffer{}
	if showPools {
		printInventoryByDutPool(w, compileInventoryReportByDutPool(bs))
	} else {
		printInventory(w, compileInventoryReport(bs))
	}
	return w.String()
}
