In infra/go run the following to activate the go environment:
eval `./env.py`

The following commands should be done while in the dashboard/frontend directory
Use gae.py to deploy:
gae.py upload -A chopsdash
gae.py switch -A chopsdash

To run a local instance:
gae.py devserver -A chopsdash
