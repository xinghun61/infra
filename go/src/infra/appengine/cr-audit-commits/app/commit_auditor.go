// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"net/http"

	"golang.org/x/net/context"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
	"go.chromium.org/luci/common/tsmon/types"
	"go.chromium.org/luci/server/router"
)

const (
	// MaxWorkers is the upper limit of how many worker goroutines to spawn.
	// There's nothing special about 16, but it seems like a reasonable
	// number of goroutines to share a cpu while waiting for i/o.
	MaxWorkers = 16
	// CommitsPerWorker is 10 commits per goroutine. To keep the life of the
	// cron job short. It is unlikely that we'll ever have to audit more
	// than this many commits in a single run of the cron job.
	CommitsPerWorker = 10
)

// workerParams are passed on to the workers for communication.
type workerParams struct {
	// To send tasks to the worker goroutines.
	jobs chan *RelevantCommit

	// To receive results from the worker goroutines.
	audited chan *RelevantCommit

	// Every worker is guaranteed to signal this channel.
	workerFinished chan bool

	// But only those that finish cleanly will signal this one.
	finishedCleanly chan bool

	// These read-only globals are meant to be read by the goroutines.
	rules []RuleSet

	clients *Clients
}

var (
	// AuditedCommits counts commits that have been scanned by this
	// handler.
	AuditedCommits = metric.NewCounter(
		"cr_audit_commits/audited",
		"Commits that have been audited by the audit app",
		&types.MetricMetadata{Units: "Commit"},
		field.Bool("violation"),
		field.String("repo"),
	)
)

// CommitAuditor is a handler meant to be periodically run to get all commits
// designated by the CommitScanner handler as needing to be audited.
//
// It expects the 'repo' form parameter to contain the name of a configured
// repository.
//
// Using a pool of worker goroutines it will execute a list of rules, gather the
// results and update the RelevantCommit entries in the datastore inside a
// transaction.
func CommitAuditor(rc *router.Context) {
	ctx, resp := rc.Context, rc.Writer
	cfg, repo, err := loadConfig(rc)
	if err != nil {
		http.Error(resp, err.Error(), 500)
		return
	}

	cs, err := initializeClients(ctx, cfg)
	if err != nil {
		http.Error(resp, err.Error(), 500)
		return
	}

	repoState := &RepoState{RepoURL: cfg.RepoURL()}
	if err := ds.Get(ctx, repoState); err != nil {
		http.Error(resp, fmt.Sprintf("The specified repository %s is not configured", repo), 400)
		return
	}

	cfgk := ds.KeyForObj(ctx, repoState)

	ap := AuditParams{
		RepoCfg:   cfg,
		RepoState: repoState,
	}

	cq := ds.NewQuery("RelevantCommit").Ancestor(cfgk).Eq("Status", auditScheduled).Limit(MaxWorkers * CommitsPerWorker)

	wp := &workerParams{rules: cfg.Rules, clients: cs}

	// Count the number of commits to be analyzed to estimate a reasonable
	// number of workers for the load.
	nCommits, err := ds.Count(ctx, cq)
	if err != nil {
		http.Error(resp, err.Error(), 500)
		return
	}
	if nCommits == 0 {
		logging.Infof(ctx, "No relevant commits to audit")
		return
	}
	logging.Infof(ctx, "Auditing %d commits", nCommits)

	// Make the number of workers proportional to the number of commits
	// that need auditing.
	nWorkers := 1 + int(nCommits)/2
	// But make sure they don't exceed a certain limit.
	if nWorkers > MaxWorkers {
		nWorkers = MaxWorkers
	}

	logging.Infof(ctx, "Starting %d workers", nWorkers)
	startAuditWorkers(ctx, ap, wp, nWorkers)
	// Send audit jobs to workers.
	ds.Run(ctx, cq, func(rc *RelevantCommit) {
		logging.Infof(ctx, "Sending %s to worker pool", rc.CommitHash)
		wp.jobs <- rc
	})
	// Signal that no more jobs will be sent.
	close(wp.jobs)
	// Wait for all workers to finish.
	for i := 0; i < nWorkers; i++ {
		<-wp.workerFinished
	}
	// We will read the relevant commits into this slice before modifying
	// them, to ensure that we don't overwrite changes that may have been
	// saved to the datastore between the time the query `cq` above ran and
	// the beginning of the transaction below.
	originalCommits := []*RelevantCommit{}
	// Read results into a map.
	auditedCommits := make(map[string]*RelevantCommit)
	close(wp.audited)
	for auditedCommit := range wp.audited {
		auditedCommits[auditedCommit.CommitHash] = auditedCommit
		originalCommits = append(originalCommits, &RelevantCommit{CommitHash: auditedCommit.CommitHash, RepoStateKey: auditedCommit.RepoStateKey})
	}

	// We save all the results produced by the workers in a single
	// transaction. We do it this way because there is rate limit of 1 QPS
	// in a single entity group. (All relevant commits for a single repo
	// are contained in a single entity group)
	err = ds.RunInTransaction(ctx, func(ctx context.Context) error {
		commitsToPut := make([]*RelevantCommit, 0, len(auditedCommits))
		if err := ds.Get(ctx, originalCommits); err != nil {
			return err
		}
		for _, currentCommit := range originalCommits {
			if auditedCommit, ok := auditedCommits[currentCommit.CommitHash]; ok {
				// Only save those that are still in the
				// auditScheduled state.
				if currentCommit.Status == auditScheduled {
					currentCommit.Status = auditCompleted
					for _, r := range auditedCommit.Result {
						if r.RuleResultStatus == ruleFailed {
							currentCommit.Status = auditCompletedWithViolation
							break
						}
					}
					// TODO(robertocn): Increment a metric
					// based on this result
					currentCommit.Result = auditedCommit.Result
					commitsToPut = append(commitsToPut, currentCommit)
				}
			}
		}
		if err := ds.Put(ctx, commitsToPut); err != nil {
			return err
		}
		for _, c := range commitsToPut {
			AuditedCommits.Add(ctx, 1, c.Status == auditCompletedWithViolation, repo)
		}
		return nil
	}, nil)

	if err != nil {
		http.Error(resp, err.Error(), 500)
	} else if len(wp.finishedCleanly) != nWorkers {
		http.Error(resp, "At least one of the audit workers did not finish cleanly", 500)
	}

	ViolationNotifier(rc)
}

// Initialize the channels and spawn the goroutines.
func startAuditWorkers(ctx context.Context, ap AuditParams, wp *workerParams, nWorkers int) {
	wp.jobs = make(chan *RelevantCommit, nWorkers*CommitsPerWorker)
	wp.audited = make(chan *RelevantCommit, nWorkers*CommitsPerWorker)
	wp.workerFinished = make(chan bool, nWorkers)
	wp.finishedCleanly = make(chan bool, nWorkers)
	for i := 0; i < nWorkers; i++ {
		go audit(ctx, i, ap, wp)
	}
}

// This is the main goroutine for each auditing goroutine.
func audit(ctx context.Context, n int, ap AuditParams, wp *workerParams) {
	defer func() { wp.workerFinished <- true }()
	for job := range wp.jobs {
		logging.Infof(ctx, "Worker %d about to run job %s", n, job.CommitHash)
		runRules(ctx, job, ap, wp)
	}
	logging.Infof(ctx, "Worker %d sees no more jobs in the channel", n)
	wp.finishedCleanly <- true
}

// The worker goroutine call this for each commit.
//
// It will run each rule on the commit, aggregate the results save them to the
// datastore entity and finally write it to the audited channel for a
// transaction to persist it when all workers are done.
//
// It swallows any panic, only logging an error in order to move to the next
// commit.
func runRules(ctx context.Context, rc *RelevantCommit, ap AuditParams, wp *workerParams) {
	defer func() {
		r := recover()
		if r != nil {
			//TODO(robertocn): Increment a metric to keep track of
			//these panics.
			logging.Errorf(ctx, "Some rule panicked while auditing %s with message: %s", rc.CommitHash, r)
		}
	}()

	for _, rs := range wp.rules {
		ars := rs.(AccountRules)
		if rs.MatchesRelevantCommit(rc) {
			ap.TriggeringAccount = ars.Account
			for _, f := range ars.Funcs {
				rc.Result = append(rc.Result, *f(ctx, &ap, rc, wp.clients))
			}
		}
	}
	wp.audited <- rc
}
