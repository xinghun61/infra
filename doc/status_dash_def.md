# ChOps Dash: Detailed Status Definitions

The Chrome Operations dashboard statuses are based on alerts that our team has set up to monitor each service. When an an alert fires a team member and the dashboard are notified on the issue.

Below is a summary of what the alerts monitor and the possible causes for a service status being red or yellow. This table will grow as our team adds more alerts to our services and more services to the status dashboard.

| **Service name**  | **Slow/experiencing disruptions** | **Service outage**
|:-----------------:|:---------------------------------:|:-------------------:
| Code Search | • search index pipeline features high<br>• Xrefs pipeline failures<br>• GoB quota issue<br>• Search index is getting old<br>• Xrefs are getting old | • the site is inaccessible |
| Commit-Queue | • CQ has generated too many errors<br>• chromium buidlers are failing<br>• commit failure rate is high<br>• taking too long to process commits or respond to a commit requesr  | • commit failure rate is so high the team considers the service unusable |
| Gerrit | • user request failure rate is high |  |
| Goma | • high qps, active jobs, access rejections, client retries<br>• high requests on unknown compilers/subprograms | • serving too many 500s<br>• necessary packages unavailable |
| Monorail | • serving a lot of 400s or 500s<br>• latency is high | • the site is inaccessible |
| Sheriff-O-Matic | • serving a lot or 400s or 500s<br>• latency is high |  |
| Swarming | • serving a lot or 400s or 500s<br>• task latency is high |  |

