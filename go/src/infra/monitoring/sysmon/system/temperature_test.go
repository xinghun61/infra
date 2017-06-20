// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package system

import (
	"testing"

	"github.com/shirou/gopsutil/host"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTemps(t *testing.T) {

	Convey("ParseMacBookTemps", t, func() {
		sensors := []host.TemperatureStat{
			{
				SensorKey:   "TA0P",
				Temperature: 11.1,
			},
			{
				SensorKey:   "TB0T",
				Temperature: 22.2,
			},
			{
				SensorKey:   "TC0P",
				Temperature: 33.3,
			},
		}
		t := parseMacBookTemps(sensors)
		So(*t.Ambient, ShouldEqual, 11.1)
		So(*t.Battery, ShouldEqual, 22.2)
		So(len(t.CPUs), ShouldEqual, 1)
		So(t.CPUs, ShouldContain, cpuTemp{Core: "TC0P", Temperature: 33.3})
	})

	Convey("ParseMacBookMissingTemps", t, func() {
		sensors := []host.TemperatureStat{
			{
				SensorKey:   "TA0P",
				Temperature: 0, // Ignored because temp is 0.
			},
			{
				SensorKey:   "ignored sensor",
				Temperature: 100.0,
			},
		}
		t := parseMacBookTemps(sensors)
		So(t.Ambient, ShouldBeNil)
		So(t.Battery, ShouldBeNil)
		So(len(t.CPUs), ShouldEqual, 0)
	})

	Convey("ParsePowerEdgeTemps", t, func() {
		// Below string was pulled from the omreport of a R720 on Win7.
		out := []byte(`
		<?xml version="1.0" encoding="UTF-8"?>
                <OMA cli="true">
			<Chassis oid="2" status="4" name="2" objtype="17" index="0" display="Main System Chassis">
				<TemperatureProbeList poid="2" count="4">
					<TemperatureProbe oid="50331659" status="2" poid="2" pobjtype="17" index="0">
						<SubType>5</SubType>
						<ProbeReading>260</ProbeReading>
						<ProbeThresholds>
							<UNRThreshold>-2147483648</UNRThreshold>
							<UCThreshold>470</UCThreshold>
							<UNCThreshold>420</UNCThreshold>
							<LNCThreshold>30</LNCThreshold>
							<LCThreshold>-70</LCThreshold>
							<LNRThreshold>-2147483648</LNRThreshold>
						</ProbeThresholds>
						<ProbeStatus>2</ProbeStatus>
						<Capabilities>
							<ProbeUNCDefSetEnabled>true</ProbeUNCDefSetEnabled>
							<ProbeLNCDefSetEnabled>true</ProbeLNCDefSetEnabled>
							<ProbeUNCSetEnabled>true</ProbeUNCSetEnabled>
							<ProbeLNCSetEnabled>true</ProbeLNCSetEnabled>
						</Capabilities>
						<ProbeLocation>System Board Inlet Temp</ProbeLocation>
					</TemperatureProbe>
					<TemperatureProbe oid="50331660" status="2" poid="2" pobjtype="17" index="1">
						<SubType>5</SubType>
						<ProbeReading>450</ProbeReading>
						<ProbeThresholds>
							<UNRThreshold>-2147483648</UNRThreshold>
							<UCThreshold>750</UCThreshold>
							<UNCThreshold>700</UNCThreshold>
							<LNCThreshold>80</LNCThreshold>
							<LCThreshold>30</LCThreshold>
							<LNRThreshold>-2147483648</LNRThreshold>
						</ProbeThresholds>
						<ProbeStatus>2</ProbeStatus>
						<Capabilities>
							<ProbeUNCDefSetEnabled>false</ProbeUNCDefSetEnabled>
							<ProbeLNCDefSetEnabled>false</ProbeLNCDefSetEnabled>
							<ProbeUNCSetEnabled>false</ProbeUNCSetEnabled>
							<ProbeLNCSetEnabled>false</ProbeLNCSetEnabled>
						</Capabilities>
						<ProbeLocation>System Board Exhaust Temp</ProbeLocation>
					</TemperatureProbe>
					<TemperatureProbe oid="50331762" status="2" poid="2" pobjtype="17" index="2">
						<SubType>5</SubType>
						<ProbeReading>780</ProbeReading>
						<ProbeThresholds>
							<UNRThreshold>-2147483648</UNRThreshold>
							<UCThreshold>1000</UCThreshold>
							<UNCThreshold>950</UNCThreshold>
							<LNCThreshold>80</LNCThreshold>
							<LCThreshold>30</LCThreshold>
							<LNRThreshold>-2147483648</LNRThreshold>
						</ProbeThresholds>
						<ProbeStatus>2</ProbeStatus>
						<Capabilities>
							<ProbeUNCDefSetEnabled>false</ProbeUNCDefSetEnabled>
							<ProbeLNCDefSetEnabled>false</ProbeLNCDefSetEnabled>
							<ProbeUNCSetEnabled>false</ProbeUNCSetEnabled>
							<ProbeLNCSetEnabled>false</ProbeLNCSetEnabled>
						</Capabilities>
						<ProbeLocation>CPU1 Temp</ProbeLocation>
					</TemperatureProbe>
					<TemperatureProbe oid="50331763" status="2" poid="2" pobjtype="17" index="3">
						<SubType>5</SubType>
						<ProbeReading>800</ProbeReading>
						<ProbeThresholds>
							<UNRThreshold>-2147483648</UNRThreshold>
							<UCThreshold>1000</UCThreshold>
							<UNCThreshold>950</UNCThreshold>
							<LNCThreshold>80</LNCThreshold>
							<LCThreshold>30</LCThreshold>
							<LNRThreshold>-2147483648</LNRThreshold>
						</ProbeThresholds>
						<ProbeStatus>2</ProbeStatus>
						<Capabilities>
							<ProbeUNCDefSetEnabled>false</ProbeUNCDefSetEnabled>
							<ProbeLNCDefSetEnabled>false</ProbeLNCDefSetEnabled>
							<ProbeUNCSetEnabled>false</ProbeUNCSetEnabled>
							<ProbeLNCSetEnabled>false</ProbeLNCSetEnabled>
						</Capabilities>
						<ProbeLocation>CPU2 Temp</ProbeLocation>
					</TemperatureProbe>
				</TemperatureProbeList>
				<ObjStatus>2</ObjStatus>
			</Chassis>
			<SMStatus>0</SMStatus>
			<OMACMDNEW>0</OMACMDNEW>
                </OMA>
                `)
		t, err := parsePowerEdgeTemps(out)
		So(err, ShouldBeNil)
		So(*t.Ambient, ShouldEqual, 26.0)
		So(t.Battery, ShouldBeNil)
		So(len(t.CPUs), ShouldEqual, 2)
		So(t.CPUs, ShouldContain, cpuTemp{Core: "CPU1 Temp", Temperature: 78.0})
		So(t.CPUs, ShouldContain, cpuTemp{Core: "CPU2 Temp", Temperature: 80.0})
	})

	Convey("ParsePowerEdgeTempsBrokenXML", t, func() {
		out := []byte("this isn't xml")
		t, err := parsePowerEdgeTemps(out)
		So(err, ShouldNotBeNil)
		So(t.Ambient, ShouldBeNil)
		So(t.Battery, ShouldBeNil)
		So(len(t.CPUs), ShouldEqual, 0)
	})

}
