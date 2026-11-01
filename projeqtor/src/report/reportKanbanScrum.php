<?php
include_once '../tool/projeqtor.php';
$user = getSessionUser();
if (! $user || ! $user->id) { htmlDisplayErrorAndDie(i18n('messageSessionWillExpire')); }
$projectId = RequestHandler::getId('projectId');
$sprintId  = RequestHandler::getId('sprintId');
$_GET['projectId'] = $projectId; $_GET['sprintId'] = $sprintId;
include_once '../tool/scrum/kanban.php';
