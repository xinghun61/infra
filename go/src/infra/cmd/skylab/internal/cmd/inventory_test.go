// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bytes"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"reflect"
	"testing"

	"github.com/kylelemons/godebug/pretty"
)

func TestCompileInventoryReport(t *testing.T) {
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
name2      -2     0     2    0      2      
dutCQ      -1     1     1    0      2      
name1      0      2     0    0      2      
dutSUITES  1      1     0    1      1      

Inventory by model
===============================================================================
Model   Avail  Good  Bad  Spare  Total  
model2  -2     0     2    0      2      
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
