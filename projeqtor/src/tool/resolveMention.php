<?php
/**
 * Resolves a @mention alias into {id, objectClass, label}.
 * Used to re-link old mentions whose
 * data-mention-* attributes were stripped by CKEditor during previous edits.
 */
require_once "../tool/projeqtor.php";
require_once "../model/IdentificationTags.php";

header('Content-Type: application/json; charset=utf-8');

$alias = isset($_REQUEST['alias']) ? $_REQUEST['alias'] : '';
$target = IdentificationTags::resolveAlias($alias);

if (!$target) {
  echo json_encode(new stdClass());
  return;
}

echo json_encode(array(
    'id'          => $target['id'],
    'objectClass' => isset($target['objectClass']) ? $target['objectClass'] : null,
    'label'       => isset($target['label']) ? $target['label'] : null,
));
?>
