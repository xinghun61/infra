# Developer information.

# Table of contents
- [Code Layout](#code-layout)
- [Environments](#environments)
- [Deploy](#deploy)
	- [Makefile](#makefile])
	- [Cron jobs](#cron-jobs)
	- [Indexes](#indexes)
- [Backups](#backups)
- [Misc](#misc)

## Code Layout

See the [Browse](BROWSE.md) doc for some explanation of how the code is laid out.

## Environments

RotaNG has the following environments
- **Staging**
  The Staging environment is configured the same as the production environment with the following differences.
	- Lives at [rota-ng-staging.googleplex.com](https://rota-ng-staging.googleplex.com)
  - Emails are sent to the google group [g/rotang-staging](https://groups.google.com/a/google.com/forum/#!forum/rotang-staging).
	- Runs in googleplex.com, this gives that only googlers can access the staging env.
	  This will change in the future to move into appspot.com.
	- The service account is `rota-ng-staging.google.com@appspot.gserviceaccount.com`
    This gives that the staging environment can not change rotation calendars in prod if not specifically allowed.
	- The staging environment does have the `chromiumcalendar@gmail.com` token.
		This gives that fetching legacy calendars works in the staging environment.
	- Handlers can check current environment using:
		```
		// IsProduction is true if the service is running in production.
		func (h *State) IsProduction() bool {
			return h.prodENV == "production"
		}

		// IsStaging is true if the service is running in staging.
		func (h *State) IsStaging() bool {
			return h.prodENV == "staging"
		}

		// IsLocal is true if the service is running in the local dev environment.
		func (h *State) IsLocal() bool {
			return h.prodENV == "local"
		}
		```
- **Production**
  The prod environment lives at [rota-ng.appspot.com](https://rota-ng.appspot.com)
	- The endpoint for all js/json rotation oncall requests.
  - What all rotation owners use to manage their rotations.
	- Changes should be tested in the staging environment before moving over to prod.

## Deploy

RotaNG uses Makefiles to deploy to the different environments.

### Dependencies
- The frontend uses `npm` to fetch it's webmodules.
  `apt install npm`

### Makefile

From the rotang folder.

- `make devserver`
  Spins up a local development server on port 8080.
- `make devserver-remote`
  Local devserver that also listens to *:8080 -> Can be reached over the network.
- `make deploy-staging`
	Pushes to the staging environment.
- `make deploy-prod`
  Pushes to the prod environment.

### Cron jobs

If changes are made to the `cron.yaml` file. It needs to be deployed to take effect.

#### Staging

`cloud app deploy cmd/app/cron.yaml --project google.com:rota-ng-staging`

#### Production

`cloud app deploy cmd/app/cron.yaml --project rota-ng`


#### Dev env.

The Development environment does not run cron jobs, they can be triggered manually but
just accessing the URLs as an admin. eg https://localhost:8080/cron/eventupdate with a
browser or wget/curl.

### Indexes

If new queries are made to Datastore the `index.yaml` file is automatically updated by
the development server. When that happens the index needs to be pushed.
If the index is not pushed/built, using the new query will fail. While the index is built
the query might also fail.

#### Staging

`gcloud app deploy cmd/app/index.yaml  --project google.com:rota-ng-staging`

#### Production

`gcloud app deploy cmd/app/index.yaml  --project rota-ng`

## Backups

The staging and production environment backs up the Rotation configuration and shifts
information once per day to GC storage buckets.

See [Exporting and Importing Entities](https://cloud.google.com/datastore/docs/export-import-entities) for
further information on how to access the information using the `gcloud` command.

### Staging

Bucket name `rota-ng-staging-backup`

### Production

Bucket name `rota-ng-production-backup`

## Misc
- [Doc with some cron/handler info](https://docs.google.com/document/d/1Zbs1w7U3rcMRmJZreMS7t-lR7E-gFgCxO7WjMBKq6JU/edit?usp=sharing)
