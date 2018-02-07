select
  IF(v.is_spam, "spam", "ham"),
  REPLACE(s.summary, '\n', '\r'),
  REPLACE(cc.content, '\n', '\r'),
  u.email,
  CONCAT("https://bugs.chromium.org/p/", p.project_name, "/issues/detail?id=", i.local_id),
  r.email
from SpamVerdict v
  join Issue i on i.id = v.issue_id
  join Comment c on c.issue_id = i.id
  join CommentContent cc on cc.comment_id = c.id
  join IssueSummary s on s.issue_id = i.id
  join Project p on p.project_id = i.project_id
  join User u on u.user_id = c.commenter_id
  join User r on r.user_id = v.user_id
where
  v.reason='manual' and v.overruled = 0;
