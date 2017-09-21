// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Binary cloudsqlhelper is a tool to simplify working with Cloud SQL databases.
package main

import (
	"flag"
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/maruel/subcommands"
	"github.com/mattes/migrate"
	"golang.org/x/net/context"

	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
)

// Options are CLI flags and arguments used by all subcommand.
type Options struct {
	DB             string   // value of '-db' flag
	ConfigPath     string   // value of '-config' flag
	MigrationsPath string   // value of '-migrations' flag
	Args           []string // all positional arguments
}

type cmdBase struct {
	subcommands.CommandRunBase
	opts Options

	// Main will be called to execute command logic.
	Main func(ctx context.Context, opts Options, conf *DBConfig, socket string) error
}

func (c *cmdBase) registerFlags(fs *flag.FlagSet) {
	fs.StringVar(&c.opts.DB, "db", "dev", "identifier of the database to operate on (from dbs.yaml file)")
	fs.StringVar(&c.opts.ConfigPath, "config", DefaultConfigPath(), "path to YAML config with list of DBs")
	fs.StringVar(&c.opts.MigrationsPath, "migrations", DefaultMigrationsPath(), "path to a directory with migration files")
}

// readDBConfig returns a config entry for given DB identifier (e.g. 'dev').
func (c *cmdBase) readDBConfig(databaseID string) (*DBConfig, error) {
	vars, err := ConfigVars()
	if err != nil {
		return nil, err
	}
	cfg, err := ReadConfig(c.opts.ConfigPath, vars)
	if err != nil {
		return nil, fmt.Errorf("failed to read the config - %s", err)
	}
	allIDs := []string{} // for the error below
	for _, dbConf := range cfg.Databases {
		allIDs = append(allIDs, fmt.Sprintf("'%s'", dbConf.ID))
		if dbConf.ID == databaseID {
			return dbConf, nil
		}
	}
	return nil, fmt.Errorf("no such DB defined in the config (have only %s)", strings.Join(allIDs, ", "))
}

// Run parses flags, sets up a context, launches local proxy and executes Main.
//
// It returns the process exit code.
func (c *cmdBase) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := CancelOnCtrlC(cli.GetContext(a, c, env))
	c.opts.Args = args

	dbConf, err := c.readDBConfig(c.opts.DB)
	if err != nil {
		logging.Errorf(ctx, "Can't read DB config - %s", err)
		return 1
	}

	err = WithLocalDBSocket(ctx, dbConf, func(ctx context.Context, socket string) error {
		return c.Main(ctx, c.opts, dbConf, socket)
	})

	if err != nil {
		logging.Errorf(ctx, "Failed - %s", err)
		return 1
	}

	return 0
}

////////////////////////////////////////////////////////////////////////////////

func proxyCmd(ctx context.Context, opts Options, conf *DBConfig, socket string) error {
	// The proxy is setup by cmdBase. Just wait until the context is canceled
	// by Ctrl+C (the handling of which is also setup by cmdBase).
	<-ctx.Done()
	return nil
}

func createCmd(ctx context.Context, opts Options, conf *DBConfig, socket string) error {
	db, err := OpenDB(ctx, socket, conf, true)
	if err != nil {
		return err
	}
	defer db.Close()
	_, err = db.ExecContext(ctx, fmt.Sprintf("CREATE DATABASE IF NOT EXISTS `%s`", conf.DB))
	return err
}

func dropCmd(ctx context.Context, opts Options, conf *DBConfig, socket string) error {
	db, err := OpenDB(ctx, socket, conf, true)
	if err != nil {
		return err
	}
	defer db.Close()
	_, err = db.ExecContext(ctx, fmt.Sprintf("DROP DATABASE IF EXISTS `%s`", conf.DB))
	return err
}

////////////////////////////////////////////////////////////////////////////////

func migrateUpCmd(ctx context.Context, opts Options, conf *DBConfig, socket string) error {
	return WithMigrate(ctx, opts.MigrationsPath, conf, socket, func(m *migrate.Migrate) error {
		ReportVersion(ctx, m)
		err := m.Up()
		switch err {
		case migrate.ErrNoChange:
			logging.Infof(ctx, "The schema is up-to-date")
			err = nil
		case nil:
			logging.Infof(ctx, "Changes applied!")
			ReportVersion(ctx, m)
		}
		return err
	})
}

func migrateDownCmd(ctx context.Context, opts Options, conf *DBConfig, socket string) error {
	return WithMigrate(ctx, opts.MigrationsPath, conf, socket, func(m *migrate.Migrate) error {
		ReportVersion(ctx, m)
		err := m.Steps(-1) // only 1! rolling back all (like m.Down does) is madness
		if err == nil {
			logging.Infof(ctx, "Changes applied!")
			ReportVersion(ctx, m)
		}
		return err
	})
}

func migrateToCmd(ctx context.Context, opts Options, conf *DBConfig, socket string) error {
	return WithMigrate(ctx, opts.MigrationsPath, conf, socket, func(m *migrate.Migrate) error {
		if len(opts.Args[0]) != 1 {
			return fmt.Errorf("expecting one positional argument with version identifier")
		}

		version, err := strconv.ParseUint(opts.Args[0], 10, 32)
		if err != nil {
			return fmt.Errorf("version identifier must be an integer")
		}

		ReportVersion(ctx, m)
		err = m.Migrate(uint(version))
		switch err {
		case migrate.ErrNoChange:
			logging.Infof(ctx, "The schema is already at that version!")
			err = nil
		case nil:
			logging.Infof(ctx, "Changes applied!")
			ReportVersion(ctx, m)
		}
		return err
	})
}

func showVersionCmd(ctx context.Context, opts Options, conf *DBConfig, socket string) error {
	return WithMigrate(ctx, opts.MigrationsPath, conf, socket, func(m *migrate.Migrate) error {
		ReportVersion(ctx, m)
		return nil
	})
}

func forceVersionCmd(ctx context.Context, opts Options, conf *DBConfig, socket string) error {
	return WithMigrate(ctx, opts.MigrationsPath, conf, socket, func(m *migrate.Migrate) error {
		if len(opts.Args[0]) != 1 {
			return fmt.Errorf("expecting one positional argument with version identifier")
		}

		version, err := strconv.ParseUint(opts.Args[0], 10, 32)
		if err != nil {
			return fmt.Errorf("version identifier must be an integer")
		}

		ReportVersion(ctx, m)
		err = m.Force(int(version))
		if err == nil {
			logging.Infof(ctx, "Changes applied!")
			ReportVersion(ctx, m)
		}
		return err
	})
}

////////////////////////////////////////////////////////////////////////////////

type cmdNewMigration struct {
	cmdBase
}

func (c *cmdNewMigration) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)
	if err := CreateEmptyMigration(c.opts.MigrationsPath); err != nil {
		logging.Errorf(ctx, "Failed - %s", err)
		return 1
	}
	return 0
}

////////////////////////////////////////////////////////////////////////////////

func GetApplication() *cli.Application {
	return &cli.Application{
		Name:  "cloudsqlhelper",
		Title: "MySQL Schema Migration Utility",
		Context: func(ctx context.Context) context.Context {
			return gologger.StdConfig.Use(ctx)
		},
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,

			{
				UsageLine: "proxy",
				ShortDesc: "launches cloud_sql_proxy",
				LongDesc:  "Launches cloud_sql_proxy and waits for Ctrl+C",
				CommandRun: func() subcommands.CommandRun {
					c := &cmdBase{Main: proxyCmd}
					c.registerFlags(&c.Flags)
					return c
				},
			},

			{
				UsageLine: "create-db",
				ShortDesc: "creates empty database",
				LongDesc:  "Creates empty database if it doesn't exist",
				CommandRun: func() subcommands.CommandRun {
					c := &cmdBase{Main: createCmd}
					c.registerFlags(&c.Flags)
					return c
				},
			},

			{
				UsageLine: "drop-db",
				ShortDesc: "drops the database",
				LongDesc:  "Drops the database if it exists",
				CommandRun: func() subcommands.CommandRun {
					c := &cmdBase{Main: dropCmd}
					c.registerFlags(&c.Flags)
					return c
				},
			},

			{
				UsageLine: "migrate-up",
				ShortDesc: "applies all pending migrations to the database",
				LongDesc: "Looks at the currently active migration version and will " +
					"migrate all the way up (applying all up migrations)",
				CommandRun: func() subcommands.CommandRun {
					c := &cmdBase{Main: migrateUpCmd}
					c.registerFlags(&c.Flags)
					return c
				},
			},

			{
				UsageLine: "migrate-down",
				ShortDesc: "rolls back the last applied migration",
				LongDesc:  "Rolls back the last applied migration (only one!)",
				CommandRun: func() subcommands.CommandRun {
					c := &cmdBase{Main: migrateDownCmd}
					c.registerFlags(&c.Flags)
					return c
				},
			},

			{
				UsageLine: "migrate-to <version>",
				ShortDesc: "migrates to the given version (up or down)",
				LongDesc:  "Migrates to the given version (up or down)",
				CommandRun: func() subcommands.CommandRun {
					c := &cmdBase{Main: migrateToCmd}
					c.registerFlags(&c.Flags)
					return c
				},
			},

			{
				UsageLine: "show-version",
				ShortDesc: "prints current schema version, as stored in the DB itself",
				LongDesc:  "Prints current schema version, as stored in the DB itself",
				CommandRun: func() subcommands.CommandRun {
					c := &cmdBase{Main: showVersionCmd}
					c.registerFlags(&c.Flags)
					return c
				},
			},

			{
				UsageLine: "force-version <version>",
				ShortDesc: "sets the schema version without doing any migrations",
				LongDesc: "Sets the schema version without doing any migrations, " +
					"intended to be used after manually fixing broken migration",
				CommandRun: func() subcommands.CommandRun {
					c := &cmdBase{Main: forceVersionCmd}
					c.registerFlags(&c.Flags)
					return c
				},
			},

			{
				UsageLine: "new-migration",
				ShortDesc: "creates empty migration",
				LongDesc:  "Creates a pair of files for new migration",
				CommandRun: func() subcommands.CommandRun {
					c := &cmdNewMigration{}
					c.registerFlags(&c.Flags)
					return c
				},
			},
		},
	}
}

func main() {
	os.Exit(subcommands.Run(GetApplication(), nil))
}
