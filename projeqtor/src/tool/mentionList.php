<?php
require_once "../tool/projeqtor.php";
require_once "../model/IdentificationTags.php";

header('Content-Type: application/json; charset=utf-8');

echo json_encode(array(
    'items' => IdentificationTags::getMentionableList()
));
?>
