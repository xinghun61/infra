# ChOps Dash: Detailed Status Definitions

The Chrome Operations dashboard statuses are based on alerts that our team has set up to monitor each service. When an an alert fires a team member and the dashboard are notified on the issue.

Below is a summary of what the alerts monitor and the possible causes for a service status being red or yellow. This table will grow as our team adds more alerts to our services and more services to the status dashboard.

| **Service name**  | **Slow/experiencing disruptions** | **Service outage**
|:-----------------:|:---------------------------------:|:-------------------:
| Code Search | <ul><li>search index pipeline features high</li><li>Xrefs pipeline failures</li><li>GoB quota issues</li><li>Search index is getting old</li><li>Xrefs are getting old</li></ul> | <ul><li>the site is inaccessible</li></ul> |
| Commit-Queue | <ul><li>CQ has generated too many errors</li><li>chromium buidlers are failing</li><li>commit failure rate is high</li><li>taking too long to process commits or respond to a commit request</li></ul>  | <ul><li>commit failure rate is so high the team considers the service unusable</li></ul> |
| Gerrit | <ul><li>user request failure rate is high</li></ul> | <ul><li></li></ul> |
| Goma | <ul><li>high qps, active jobs, access rejections, client retries</li><li>high requests on unknown compilers/subprograms</li></ul> | <ul><li>serving too many 500s</li><li>necessary packages unavailable</li></ul> |
| Monorail | <ul><li>serving a lot of 400s or 500s</li><li>latency is high</li></ul> | <ul><li>the site is inaccessible</li></ul> |
| Sheriff-O-Matic | <ul><li>serving a lot or 400s or 500s</li><li>latency is high</li></ul> | <ul><li></li></ul> |
| Swarming | <ul><li>serving a lot or 400s or 500s</li><li>task latency is high</li></ul> | <ul><li></li></ul> |

