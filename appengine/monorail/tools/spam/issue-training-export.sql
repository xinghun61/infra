select IF(i.is_spam, "spam", "ham"), REPLACE(s.summary, '\n', '\r'), REPLACE(c.content, '\n', '\r'), u.email
from SpamVerdict v
join Issue i on i.id = v.issue_id
join IssueSummary s on s.issue_id = i.id
join Project p on p.project_id = i.project_id
join Comment c on c.issue_id = i.id
join User u on u.user_id = c.commenter_id
where
reason="manual" and overruled=0
