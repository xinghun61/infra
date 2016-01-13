# sheriff-o-matic

This is the polymer 1.0 rewrite.

To run locally from an infra.git checkout:
```
../../luci/appengine/components/tools/gae.py devserver --app-dir=.
```

To run tests:
```
xvfb-run -a wct
```

To deploy:
```
gcloud preview app --project=google.com:sheriffo deploy app.yaml
```
