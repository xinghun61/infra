// Copyright (c) 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package docker

import (
	"bytes"
	"encoding/json"
	"strings"
	"sync"
	"time"

	dockerTypes "github.com/docker/docker/api/types"
	"github.com/docker/docker/client"

	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	tsmonTypes "github.com/luci/luci-go/common/tsmon/types"

	"golang.org/x/net/context"
)

var (
	statusMetric = metric.NewString("dev/container/status",
		"Status (running, stopped, etc.) of a container.",
		nil,
		field.String("name"),
		field.String("hostname"))

	uptimeMetric = metric.NewFloat("dev/container/uptime",
		"Uptime (in seconds) of a container.",
		&tsmonTypes.MetricMetadata{Units: tsmonTypes.Seconds},
		field.String("name"))

	memUsedMetric = metric.NewInt("dev/container/mem/used",
		"Memory in used by a container.",
		&tsmonTypes.MetricMetadata{Units: tsmonTypes.Bytes},
		field.String("name"))
	memTotalMetric = metric.NewInt("dev/container/mem/total",
		"Total memory avaialable to a container.",
		&tsmonTypes.MetricMetadata{Units: tsmonTypes.Bytes},
		field.String("name"))

	netDownMetric = metric.NewInt("dev/container/net/down",
		"Total bytes of network ingress for the container.",
		&tsmonTypes.MetricMetadata{Units: tsmonTypes.Bytes},
		field.String("name"))
	netUpMetric = metric.NewInt("dev/container/net/up",
		"Total bytes of network egress for the container.",
		&tsmonTypes.MetricMetadata{Units: tsmonTypes.Bytes},
		field.String("name"))

	allMetrics = []tsmonTypes.Metric{
		statusMetric,
		uptimeMetric,
		memUsedMetric,
		memTotalMetric,
		netDownMetric,
		netUpMetric,
	}
)

// The following is a subset of the fields contained in the json blob returned
// when querying the engine for a container's stats. Only the fields we care
// about are listed here. See the following for format of the json:
// https://github.com/docker/docker/blob/v1.13.0/docs/api/v1.24.md#get-container-stats-based-on-resource-usage
type containerStats struct {
	Name     string
	Memory   memoryStats `json:"memory_stats"`
	Networks struct {
		Eth0 struct {
			RxBytes int64 `json:"rx_bytes"`
			TxBytes int64 `json:"tx_bytes"`
		}
	}
}
type memoryStats struct {
	Usage int64
	Limit int64
}

func updateContainerMetrics(ctx context.Context, c dockerTypes.Container, cInfo dockerTypes.ContainerJSON, cStatsJSON dockerTypes.ContainerStats) error {
	// Remove leading slash from container name.
	cName := strings.TrimPrefix(c.Names[0], "/")
	cState := c.State
	cHostname := cInfo.Config.Hostname
	statusMetric.Set(ctx, cState, cName, cHostname)
	startTime, err := time.Parse(time.RFC3339Nano, cInfo.State.StartedAt)
	if err != nil {
		return err
	}
	uptime := clock.Now(ctx).Sub(startTime).Seconds()
	uptimeMetric.Set(ctx, uptime, cName)

	buff := new(bytes.Buffer)
	defer cStatsJSON.Body.Close()
	if _, err := buff.ReadFrom(cStatsJSON.Body); err != nil {
		return err
	}
	cStats := &containerStats{}
	if err := json.Unmarshal(buff.Bytes(), cStats); err != nil {
		return err
	}

	netUp := cStats.Networks.Eth0.TxBytes
	netDown := cStats.Networks.Eth0.RxBytes
	memTotal := cStats.Memory.Limit
	memUsed := cStats.Memory.Usage

	memUsedMetric.Set(ctx, memUsed, cName)
	memTotalMetric.Set(ctx, memTotal, cName)
	netUpMetric.Set(ctx, netUp, cName)
	netDownMetric.Set(ctx, netDown, cName)
	return nil
}

func inspectContainer(ctx context.Context, dockerClient *client.Client, c dockerTypes.Container) error {
	cInfo, err := dockerClient.ContainerInspect(ctx, c.ID)
	if err != nil {
		return err
	}

	// The docker client returns a stream of raw json for a container's stats.
	cStatsJSON, err := dockerClient.ContainerStats(ctx, c.ID, false)
	if err != nil {
		return err
	}

	return updateContainerMetrics(ctx, c, cInfo, cStatsJSON)
}

func update(ctx context.Context) error {
	dockerClient, err := client.NewEnvClient()
	if err != nil {
		return err
	}

	if _, err = dockerClient.Ping(ctx); err != nil {
		// Don't log an error if the ping failed. Most bots don't have
		// the docker engine installed and running.
		return nil
	}

	containers, err := dockerClient.ContainerList(ctx, dockerTypes.ContainerListOptions{All: true})
	if err != nil {
		return err
	}

	// Inspect each container in parallel. This is much faster than doing so in serial.
	wg := sync.WaitGroup{}
	for _, c := range containers {
		wg.Add(1)
		go func(c dockerTypes.Container) {
			defer wg.Done()
			if err := inspectContainer(ctx, dockerClient, c); err != nil {
				logging.Errorf(ctx, "Failed to query docker engine: %s", err)
			}
		}(c)
	}
	wg.Wait()

	return nil
}

// Register adds tsmon callbacks to set docker metrics.
func Register() {
	tsmon.RegisterGlobalCallback(func(ctx context.Context) {
		if err := update(ctx); err != nil {
			logging.Errorf(ctx, "Failed to update Docker metrics: %s", err)
		}
	}, allMetrics...)
}
