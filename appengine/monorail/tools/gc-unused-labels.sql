-- Garbage collect LabelDef rows from all projects where:
-- 1. The label is not currently in use (it does not join to Issue2Label).
-- 2. The label is not a well-known label (it does not have a rank).
-- There are currently about 1500 such labels in the prod database.

CREATE TABLE LabelDefToDelete (id INT);

INSERT INTO LabelDefToDelete (id)
  SELECT id FROM LabelDef
    LEFT JOIN Issue2Label ON LabelDef.id = Issue2Label.label_id
    WHERE issue_id IS NULL
    AND rank IS NULL;

DELETE FROM LabelDef
  WHERE id IN (SELECT * FROM LabelDefToDelete)
  LIMIT 2000;

