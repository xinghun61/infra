// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package scheduler

import (
	"time"

	"infra/qscheduler/qslib/protos"
	"infra/qscheduler/qslib/tutils"
)

// Config represents configuration fields that affect the behavior
// the quota scheduler pool.
type Config struct {
	// AccountConfigs is a map of per-account AccountConfig.
	AccountConfigs map[AccountID]*AccountConfig

	// DisablePreemption, if true, causes scheduler to never preempt
	// any tasks.
	DisablePreemption bool

	// BotExpiration is the duration after which a bot will no longer be
	// considered idle, if the scheduler doesn't receive any assignment requests
	// for it.
	//
	// If 0 or unspecified, defaults to 300 seconds.
	BotExpiration time.Duration
}

// ToProto convers a config to proto representation.
func (c *Config) ToProto() *protos.SchedulerConfig {
	p := &protos.SchedulerConfig{
		AccountConfigs:    make(map[string]*protos.AccountConfig),
		DisablePreemption: c.DisablePreemption,
		BotExpiration:     tutils.DurationProto(c.BotExpiration),
	}
	for aid, ac := range c.AccountConfigs {
		p.AccountConfigs[string(aid)] = &protos.AccountConfig{
			ChargeRate:       ac.ChargeRate[:],
			DisableFreeTasks: ac.DisableFreeTasks,
			MaxChargeSeconds: ac.MaxChargeSeconds,
			MaxFanout:        ac.MaxFanout,
		}
	}
	return p
}

// NewConfig creates an returns a new Config instance.
func NewConfig() *Config {
	return &Config{
		AccountConfigs: make(map[AccountID]*AccountConfig),
	}
}

// NewConfigFromProto creates an returns a new Config instance from a
// proto representation.
func NewConfigFromProto(p *protos.SchedulerConfig) *Config {
	c := NewConfig()
	if p.BotExpiration != nil {
		c.BotExpiration = tutils.Duration(p.BotExpiration)
	}
	c.DisablePreemption = p.DisablePreemption
	for aid, ac := range p.AccountConfigs {
		c.AccountConfigs[AccountID(aid)] = NewAccountConfig(
			int(ac.MaxFanout), ac.MaxChargeSeconds, ac.ChargeRate, ac.DisableFreeTasks)
	}
	return c
}
