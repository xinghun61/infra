// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package system

import (
	"encoding/xml"
	"fmt"
	"os/exec"
	"strings"

	"github.com/shirou/gopsutil/host"
	"golang.org/x/net/context"
)

type temps struct {
	// Assign as pointers to differentiate between unassigned/nil and 0.
	Ambient *float64
	Battery *float64
	CPUs    []cpuTemp
}
type cpuTemp struct {
	Core        string
	Temperature float64
}

type chassisReport struct {
	XMLName xml.Name `xml:"OMA"`
	Chassis chassis
}
type chassis struct {
	XMLName              xml.Name `xml:"Chassis"`
	TemperatureProbeList temperatureProbeList
}
type temperatureProbeList struct {
	XMLName          xml.Name `xml:"TemperatureProbeList"`
	TemperatureProbe []temperatureProbe
}
type temperatureProbe struct {
	XMLName         xml.Name `xml:"TemperatureProbe"`
	SubType         []byte
	ProbeReading    float64
	ProbeThresholds []byte
	ProbeStatus     int64
	Capabilities    []byte
	ProbeLocation   string
}

func getPowerEdgeTemps(c context.Context) (temps, error) {
	// The gopsutil pkg is unable to get temp readings for Dell servers.
	// Instead, use the Dell utility omreport. It should be installed on all servers.
	// Dump the report in xml for easier parsing.
	cmd := exec.CommandContext(c, "omreport", "chassis", "temps", "-fmt", "xml")
	out, err := cmd.Output()
	if err != nil {
		return temps{}, err
	}
	return parsePowerEdgeTemps(out)
}

func parsePowerEdgeTemps(out []byte) (temps, error) {
	var t temps
	var r chassisReport
	if err := xml.Unmarshal(out, &r); err != nil {
		return t, err
	}
	for _, p := range r.Chassis.TemperatureProbeList.TemperatureProbe {
		sensor := p.ProbeLocation
		// omreport reports temps in tenths of a degree.
		temp := p.ProbeReading / 10.0
		if sensor == "System Board Inlet Temp" {
			t.Ambient = &temp
		} else if strings.HasPrefix(sensor, "CPU") {
			t.CPUs = append(t.CPUs, cpuTemp{Core: sensor, Temperature: temp})
		}
	}
	return t, nil
}

func getMacBookTemps(c context.Context) (temps, error) {
	sensors, err := host.SensorsTemperatures()
	if err != nil {
		return temps{}, err
	}
	return parseMacBookTemps(sensors), nil
}
func parseMacBookTemps(sensors []host.TemperatureStat) temps {
	var t temps
	for _, s := range sensors {
		sensor := s.SensorKey
		temp := s.Temperature
		if temp == 0 {
			// Some sensors report 0 degrees. Safe to say it won't drop below freezing
			// in our data centers, so just skip these.
			continue
		}
		// See https://github.com/shirou/gopsutil/blob/master/host/include/smc.h
		// and https://github.com/Chris911/iStats/blob/master/ext/osx_stats/smc.h
		// for sensor name mapping.
		switch sensor {
		case "TA0P":
			t.Ambient = &temp
		case "TB0T":
			t.Battery = &temp
		case "TC0P":
			t.CPUs = append(t.CPUs, cpuTemp{Core: sensor, Temperature: temp})
		}
	}
	return t
}

func getTemps(c context.Context, model string) (temps, error) {
	// TODO(crbug.com/734271): Add support for more models.
	if strings.HasPrefix(model, "PowerEdge") {
		return getPowerEdgeTemps(c)
	} else if strings.HasPrefix(model, "MacBook") {
		return getMacBookTemps(c)
	}
	return temps{}, fmt.Errorf("Unable to get temps for hardware model: %s", model)
}
