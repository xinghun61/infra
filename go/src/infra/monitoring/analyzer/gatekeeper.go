package analyzer

import (
	"golang.org/x/net/context"

	"go.chromium.org/luci/common/logging"

	"infra/monitoring/messages"
)

// GatekeeperRules implements the rule checks that gatekeeper performs
// on failures to determine if the failure should close the tree.
type GatekeeperRules struct {
	cfgs     []*messages.GatekeeperConfig
	treeCfgs map[string][]messages.TreeMasterConfig
}

// NewGatekeeperRules returns a new instance of GatekeeperRules initialized
// with cfg.
func NewGatekeeperRules(ctx context.Context, cfgs []*messages.GatekeeperConfig, treeCfgs map[string][]messages.TreeMasterConfig) *GatekeeperRules {
	for _, cfg := range cfgs {
		for master, masterCfgs := range cfg.Masters {
			if len(masterCfgs) != 1 {
				logging.Errorf(ctx, "Multiple configs for master: %s", master)
			}
		}
	}
	return &GatekeeperRules{cfgs, treeCfgs}
}

func (r *GatekeeperRules) findMaster(master *messages.MasterLocation) ([]messages.MasterConfig, bool) {
	for _, cfg := range r.cfgs {
		if mcs, ok := cfg.Masters[master.String()]; ok {
			return mcs, ok
		}
	}
	return nil, false
}

func (r *GatekeeperRules) getAllowedBuilders(tree string, master *messages.MasterLocation) []string {
	allowed := []string{}

	for _, cfg := range r.treeCfgs[tree] {
		allowed = append(allowed, cfg.Masters[*master]...)
	}

	return allowed
}

// WouldCloseTree returns true if a step failure on given builder/master would
// cause it to close the tree.
func (r *GatekeeperRules) WouldCloseTree(ctx context.Context, master *messages.MasterLocation, builder, step string) bool {
	mcs, ok := r.findMaster(master)
	if !ok {
		logging.Errorf(ctx, "Missing master cfg: %s", master)
		return false
	}
	mc := mcs[0]
	bc, ok := mc.Builders[builder]
	if !ok {
		bc, ok = mc.Builders["*"]
		if !ok {
			return false
		}
	}

	// TODO: Check for cfg.Categories
	for _, xstep := range bc.ExcludedSteps {
		if xstep == step {
			return false
		}
	}

	csteps := []string{}
	csteps = append(csteps, bc.ClosingSteps...)
	csteps = append(csteps, bc.ClosingOptional...)

	for _, cs := range csteps {
		if cs == "*" || cs == step {
			return true
		}
	}

	return false
}

func contains(arr []string, s string) bool {
	for _, itm := range arr {
		if itm == s {
			return true
		}
	}

	return false
}

// ExcludeBuilder returns true if a builder should be ignored.
func (r *GatekeeperRules) ExcludeBuilder(ctx context.Context, tree string, master *messages.MasterLocation, builder string) bool {
	mcs, ok := r.findMaster(master)
	if !ok {
		logging.Errorf(ctx, "Can't filter unknown master %s (tree %s)", master, tree)
		return false
	}
	mc := mcs[0]

	allowedBuilders := r.getAllowedBuilders(tree, master)
	if !(contains(allowedBuilders, "*") || contains(allowedBuilders, builder)) {
		return true
	}

	for _, ebName := range mc.ExcludedBuilders {
		if ebName == "*" || ebName == builder {
			return true
		}
	}

	return false
}

// ExcludeFailure returns true if a step failure whould be ignored.
func (r *GatekeeperRules) ExcludeFailure(ctx context.Context, tree string, master *messages.MasterLocation, builder, step string) bool {
	if r.ExcludeBuilder(ctx, tree, master, builder) {
		return true
	}

	mcs, ok := r.findMaster(master)
	if !ok {
		logging.Errorf(ctx, "Can't filter unknown master %s (tree %s)", master, tree)
		return false
	}
	mc := mcs[0]

	for _, ebName := range mc.ExcludedBuilders {
		if ebName == "*" || ebName == builder {
			return true
		}
	}

	// Not clear that builder_alerts even looks at the rest of these conditions
	// even though they're specified in gatekeeper.json
	for _, s := range mc.ExcludedSteps {
		if step == s {
			return true
		}
	}

	bc, ok := mc.Builders[builder]
	if !ok {
		if bc, ok = mc.Builders["*"]; !ok {
			logging.Errorf(ctx, "Unknown %s builder %s", master, builder)
			return true
		}
	}

	for _, esName := range bc.ExcludedSteps {
		if esName == step || esName == "*" {
			return true
		}
	}

	return false
}
