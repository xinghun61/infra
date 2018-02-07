select
  IF(v.is_spam, "spam", "ham"),
  "",
  REPLACE(cc.content, '\n', '\r'),
  u.email,
  CONCAT("https://bugs.chromium.org/p/", p.project_name, "/issues/detail?id=", i.local_id),
  r.email
from SpamVerdict v
  join Comment c on c.id = v.comment_id
  join CommentContent cc on cc.comment_id = c.id
  join Project p on p.project_id = c.project_id
  join Issue i on i.id=c.issue_id
  join User u on u.user_id = c.commenter_id
  join User r on r.user_id = v.user_id
where
  v.reason='manual' and v.overruled = 0;
