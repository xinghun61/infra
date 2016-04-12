package analyzer

import (
	"strings"

	"infra/monitoring/messages"
)

// GatekeeperRules implements the rule checks that gatekeeper performs
// on failures to determine if the failure should close the tree.
type GatekeeperRules struct {
	cfg messages.GatekeeperConfig
}

// NewGatekeeperRules returns a new instance of GatekeeperRules initialized
// with cfg.
func NewGatekeeperRules(cfg messages.GatekeeperConfig) *GatekeeperRules {
	ret := &GatekeeperRules{cfg}
	for masterURL, masterCfgs := range cfg.Masters {
		if len(masterCfgs) != 1 {
			log.Errorf("Multiple configs for master: %s", masterURL)
		}
		parts := strings.Split(masterURL, "/")
		masterName := parts[len(parts)-1]
		ret.cfg.Masters[masterName] = masterCfgs
	}
	return ret
}

// WouldCloseTree returns true if a step failure on given builder/master would
// cause it to close the tree.
func (r *GatekeeperRules) WouldCloseTree(master, builder, step string) bool {
	mcs, ok := r.cfg.Masters[master]
	if !ok {
		log.Errorf("Missing master cfg: %s", master)
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

// ExcludeFailure returns true if a step failure whould be ignored.
func (r *GatekeeperRules) ExcludeFailure(master, builder, step string) bool {
	mcs, ok := r.cfg.Masters[master]
	if !ok {
		log.Errorf("Can't filter unknown master %s", master)
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
			log.Warningf("Unknown %s builder %s", master, builder)
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
