<?php
require_once('../tool/projeqtor.php');
$user = getSessionUser();
if (! $user || ! $user->id) { htmlDisplayErrorAndDie(i18n('messageSessionWillExpire')); }
header('Content-Type: application/json; charset=utf-8');

$action    = RequestHandler::getValue('action');
$projectId = RequestHandler::getId('projectId');
$sprintId  = RequestHandler::getId('sprintId');
$ownerId   = RequestHandler::getId('ownerId');
$search    = RequestHandler::getValue('search');
$sort      = RequestHandler::getValue('sort');

if (! $projectId) { echo json_encode(['status'=>'KO','message'=>'Missing projectId']); exit; }

$prefix = Parameter::getGlobalParameter('paramDbPrefix');

function firstStatusByIdle($idle) {
  $st = new Status();
  $lst = $st->getSqlElementsFromCriteria(array('idle'=>'0'), null, null, 'sortOrder asc');
  foreach ($lst as $s) { if ((int)$s->setIdleStatus === (int)$idle) return $s->id; }
  return null;
}

if ($action==='list') {
  $where = " where us.idProject=".Sql::fmtId($projectId)." and us.idle=0 ";
  if ($sprintId) $where .= " and us.idSprint=".Sql::fmtId($sprintId);
  if ($ownerId)  $where .= " and us.idUser=".Sql::fmtId($ownerId);
  if ($search)   $where .= " and (us.name like ".Sql::str('%'.$search.'%')." or us.description like ".Sql::str('%'.$search.'%').")";

  $order = " order by us.id desc ";
  $allowedSort = array('id desc'=>"us.id desc",'id asc'=>"us.id asc",'name asc'=>"us.name asc",'storyPoints desc'=>"us.storyPoints desc",'statusName asc'=>"s.name asc");
  if ($sort && isset($allowedSort[$sort])) $order = " order by ".$allowedSort[$sort]." ";

  $qry = "select us.id, us.name, us.storyPoints, us.idStatus, ep.name as epicName, u.fullName as owner, s.name as statusName, s.setIdleStatus
          from ${prefix}userstory us
          left join ${prefix}epic ep on ep.id=us.idEpic
          left join ${prefix}user u on u.id=us.idUser
          left join ${prefix}status s on s.id=us.idStatus
          $where $order";
  $res = Sql::query($qry);
  $cards = array();
  while ($row = Sql::fetchLine($res)) {
    $r = array_change_key_case($row, CASE_LOWER);
    $cards[] = array(
      'id'=>intval($r['id']),
      'name'=>$r['name'],
      'storyPoints'=> isset($r['storypoints']) ? intval($r['storypoints']) : null,
      'epicName'=>$r['epicname'],
      'owner'=>$r['owner'],
      'statusId'=> isset($r['idstatus']) ? intval($r['idstatus']) : null,
      'statusName'=>$r['statusname'],
      'isDone'=> isset($r['setidlestatus']) ? ((int)$r['setidlestatus']===1) : false
    );
  }
  echo json_encode(['status'=>'OK','cards'=>$cards]); exit;
}

if ($action==='move') {
  $usId = RequestHandler::getId('userStoryId');
  $target = RequestHandler::getValue('target'); // "open" or "done"
  if (! $projectId || ! $usId || ! in_array($target,['open','done'])) { echo json_encode(['status'=>'KO','message'=>'Missing data']); exit; }

  $us = new UserStory($usId);
  if (! $us->id or $us->idProject != $projectId) { echo json_encode(['status'=>'KO','message'=>'Forbidden']); exit; }
  if ($sprintId && $us->idSprint != $sprintId) { echo json_encode(['status'=>'KO','message'=>'Not in sprint']); exit; }

  if (securityGetAccessRightYesNo ( "menuUserStory", "update", $us ) != "YES") {
    echo json_encode(['status'=>'KO','message'=>'No right to update UserStory']); exit;
  }

  $targetStatus = ($target==='done') ? firstStatusByIdle(1) : firstStatusByIdle(0);
  if (! $targetStatus) { echo json_encode(['status'=>'KO','message'=>'No suitable status found']); exit; }
  $us->idStatus = $targetStatus;
  $res = $us->save();
  echo json_encode(['status'=> (getLastOperationStatus($res)=='OK' ? 'OK' : 'KO')]); exit;
}

echo json_encode(['status'=>'KO','message'=>'Unknown action']);