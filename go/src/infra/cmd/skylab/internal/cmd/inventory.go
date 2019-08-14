// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"io"
	"sort"
	"strings"
	"text/tabwriter"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"
	"infra/libs/skylab/inventory"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/flag"
	"go.chromium.org/luci/grpc/prpc"
)

// Inventory subcommand: Print host inventory.
var Inventory = &subcommands.Command{
	UsageLine: "inventory [-dev] [-show-pools] [-labs N]",
	ShortDesc: "print DUT inventory",
	LongDesc: `Print a summary of the DUT inventory.

This is the equivalent of the inventory email in Autotest.
`,
	CommandRun: func() subcommands.CommandRun {
		c := &inventoryRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.BoolVar(&c.showPools, "show-pools", false, "Show count of managed pools within each model.")
		c.Flags.Var(flag.CommaList(&c.labs), "labs",
			`Restrict results to specific labs.  This should be a number, and
multiple labs can be specified separated with commas.  For example,
labs chromeos2 and chromeos4 can be specified with 2,4.`)
		return c
	},
}

type inventoryRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
	showPools bool
	labs      []string
}

func (c *inventoryRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s: %s\n", progName, err)
		return 1
	}
	return 0
}

func (c *inventoryRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	ctx := cli.GetContext(a, c, env)
	hc, err := newHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return err
	}
	e := c.envFlags.Env()
	tc := fleet.NewTrackerPRPCClient(&prpc.Client{
		C:       hc,
		Host:    e.AdminService,
		Options: site.DefaultPRPCOptions,
	})
	res, err := tc.SummarizeBots(ctx, &fleet.SummarizeBotsRequest{})
	if err != nil {
		return err
	}
	bs := res.GetBots()
	if c.showPools {
		r := compileInventoryReportByDutPool(filterBots(bs, c.labs))
		_ = printInventoryByDutPool(a.GetOut(), r)
		return nil
	}
	r := compileInventoryReport(filterBots(bs, c.labs))
	_ = printInventory(a.GetOut(), r)
	return nil
}

// filterBots filters for the bots in the given labs.  labs should be
// a slice of strings of lab numbers.  If labs is empty, no filtering
// is done.
func filterBots(bs []*fleet.BotSummary, labs []string) []*fleet.BotSummary {
	if len(labs) == 0 {
		return bs
	}
	keep := make(map[string]bool, len(labs))
	for _, lab := range labs {
		keep[lab] = true
	}
	var new []*fleet.BotSummary
	for _, b := range bs {
		name := b.GetDimensions().GetDutName()
		if n := getBotLabNumber(name); keep[n] {
			new = append(new, b)
		}
	}
	return new
}

// getBotLabNumber returns the lab number for the DUT name as a
// string.  For example, "4" for "chromeos4" DUTs.  The empty string
// is returned if the lab cannot be determined.
func getBotLabNumber(n string) string {
	if !strings.HasPrefix(n, "chromeos") {
		return ""
	}
	i := len("chromeos")
	j := strings.IndexByte(n[i:], '-')
	if j == -1 {
		return ""
	}
	return n[i : i+j]
}

// inventoryReport contains the compiled status of the inventory
// state.
type inventoryReport struct {
	labs   []*inventoryCount
	models []*inventoryCount
}

// inventoryCount contains the inventory count for some subset of the
// inventory.
type inventoryCount struct {
	name  string
	good  int
	bad   int
	spare int
}

func (ic inventoryCount) available() int {
	// TODO(ayatane): Quota scheduler only DUTs do not have a
	// spares pool, which messes up the availability count with
	// regard to how models are prioritized for DUT repair.  We
	// assume some minimum size of spares that we can tolerate for
	// each model.
	// https://sites.google.com/a/google.com/chromeos/for-team-members/infrastructure/chromeos-admin/creating-pools
	spare := 6
	if ic.spare != 0 {
		spare = ic.spare
	}
	if t := ic.total(); t < spare {
		spare = t
	}
	return spare - ic.bad
}

func (ic inventoryCount) total() int {
	return ic.good + ic.bad
}

type inventoryMap struct {
	// This is wrapped in a struct to prevent accidentally
	// bypassing the get method.
	m map[string]*inventoryCount
}

func newInventoryMap() inventoryMap {
	return inventoryMap{
		m: make(map[string]*inventoryCount),
	}
}

// Get gets the inventoryCount from the map, allocating a new
// object if needed.
func (m inventoryMap) get(key string) *inventoryCount {
	if ic := m.m[key]; ic != nil {
		return ic
	}
	ic := &inventoryCount{name: key}
	m.m[key] = ic
	return ic
}

// Slice returns a sorted slice of the map's contents.
func (m inventoryMap) slice() []*inventoryCount {
	s := make([]*inventoryCount, 0, len(m.m))
	for _, ic := range m.m {
		s = append(s, ic)
	}
	sort.Slice(s, func(i, j int) bool { return s[i].available() < s[j].available() })
	return s
}

type poolStateCount struct {
	ready int
	total int
}

// modelPools contains the count of DUT state for managed pool.
type modelPools struct {
	name  string
	pools map[inventory.SchedulableLabels_DUTPool]poolStateCount
}

// modelPoolsMap maps model name and modelPools
type modelPoolsMap struct {
	m map[string]*modelPools
}

func newModelPoolsMap() modelPoolsMap {
	return modelPoolsMap{
		m: make(map[string]*modelPools),
	}
}

// Get is a mutation of inventoryMap's get method, allocating a new
// modelPools if necessary.
func (m modelPoolsMap) get(key string) *modelPools {
	if mp := m.m[key]; mp != nil {
		return mp
	}
	mp := &modelPools{
		name:  key,
		pools: make(map[inventory.SchedulableLabels_DUTPool]poolStateCount),
	}
	m.m[key] = mp
	return mp
}

// Slice sorts the slice by the alphabetical order of model name.
func (m modelPoolsMap) slice() []*modelPools {
	s := make([]*modelPools, 0, len(m.m))
	for _, mp := range m.m {
		s = append(s, mp)
	}
	sort.Slice(s, func(i, j int) bool { return s[i].name < s[j].name })
	return s
}

func compileInventoryReport(bs []*fleet.BotSummary) *inventoryReport {
	labCounts := newInventoryMap()
	modelCounts := newInventoryMap()
	for _, b := range bs {
		d := b.GetDimensions()
		mc := modelCounts.get(d.GetModel())
		addBotCount(mc, b)
		lc := labCounts.get(botLocation(b))
		addBotCount(lc, b)
	}
	return &inventoryReport{
		labs:   labCounts.slice(),
		models: modelCounts.slice(),
	}
}

func compileInventoryReportByDutPool(bs []*fleet.BotSummary) []*modelPools {
	modelCountsByPool := newModelPoolsMap()
	for _, b := range bs {
		d := b.GetDimensions()
		mcbp := modelCountsByPool.get(d.GetModel())
		addDutStateCount(mcbp, b)
	}
	return modelCountsByPool.slice()
}

func botLocation(b *fleet.BotSummary) string {
	n := b.GetDimensions().GetDutName()
	if i := strings.IndexByte(n, '-'); i > -1 {
		return n[:i]
	}
	return n
}

func addBotCount(ic *inventoryCount, b *fleet.BotSummary) {
	if b.Health == fleet.Health_Healthy {
		ic.good++
	} else {
		ic.bad++
	}
	if isSuites(b) {
		ic.spare++
	}
}

func addDutStateCount(mp *modelPools, b *fleet.BotSummary) {
	pools := b.GetDimensions().GetPools()
	for _, p := range pools {
		i, ok := inventory.SchedulableLabels_DUTPool_value[p]
		if !ok {
			continue
		}
		dutPoolVal := inventory.SchedulableLabels_DUTPool(i)
		psc := mp.pools[dutPoolVal]
		psc.total++
		if b.GetDutState() == fleet.DutState_Ready {
			psc.ready++
		}
		mp.pools[dutPoolVal] = psc
	}
}

// isSuites returns true if the bot is in the suites pool
func isSuites(b *fleet.BotSummary) bool {
	ps := b.GetDimensions().GetPools()
	suitesPool := inventory.SchedulableLabels_DUT_POOL_SUITES.String()
	for _, p := range ps {
		if p == suitesPool {
			return true
		}
	}
	return false
}

func printInventory(w io.Writer, r *inventoryReport) error {
	tw := tabwriter.NewWriter(w, 0, 0, 2, ' ', 0)
	fmt.Fprintln(tw, "Inventory by location")
	fmt.Fprintln(tw, "===============================================================================")
	fmt.Fprintf(tw, "Location\tAvail\tGood\tBad\tSpare\tTotal\t\n")
	for _, i := range r.labs {
		fmt.Fprintf(tw, "%s\t%d\t%d\t%d\t%d\t%d\t\n",
			i.name, i.available(), i.good, i.bad, i.spare, i.total())
	}
	fmt.Fprintln(tw)
	fmt.Fprintln(tw, "Inventory by model")
	fmt.Fprintln(tw, "===============================================================================")
	fmt.Fprintf(tw, "Model\tAvail\tGood\tBad\tSpare\tTotal\t\n")
	for _, i := range r.models {
		fmt.Fprintf(tw, "%s\t%d\t%d\t%d\t%d\t%d\t\n",
			i.name, i.available(), i.good, i.bad, i.spare, i.total())
	}
	return tw.Flush()
}

// getNonEmptyPools filters out those DUT pools whose output is zeros crossing
// all rows.
func getNonEmptyPools(mps []*modelPools) []inventory.SchedulableLabels_DUTPool {
	pool := make(map[inventory.SchedulableLabels_DUTPool]bool)
	new := []inventory.SchedulableLabels_DUTPool{}
	for _, mp := range mps {
		for p := range mp.pools {
			if pool[p] {
				continue
			}
			pool[p] = true
			new = append(new, p)
		}
	}
	sort.Slice(new, func(i, j int) bool { return new[i] < new[j] })
	return new
}

func printInventoryByDutPool(w io.Writer, m []*modelPools) error {
	tw := tabwriter.NewWriter(w, 0, 0, 2, ' ', 0)
	fmt.Fprintln(tw, "DUT Pool Count by model")
	fmt.Fprintln(tw, "===============================================================================")
	fmt.Fprintf(tw, "Model\t")
	pools := getNonEmptyPools(m)
	for _, p := range pools {
		fmt.Fprintf(tw, "%s\t", p)
	}
	fmt.Fprintf(tw, "\n")
	for _, i := range m {
		fmt.Fprintf(tw, "%s\t", i.name)
		for _, p := range pools {
			fmt.Fprintf(tw, "%d/%d\t", i.pools[p].ready, i.pools[p].total)
		}
		fmt.Fprintln(tw)
	}
	return tw.Flush()
}
