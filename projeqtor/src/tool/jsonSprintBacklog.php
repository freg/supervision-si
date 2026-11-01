<?PHP
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 *
 * ProjeQtOr is free software: you can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option)
 * any later version.
 *
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/** ===========================================================================
 * Get the list of objects, in Json format, to display the grid list
 */
require_once "../tool/projeqtor.php";
session_write_close();
scriptLog('   ->/tool/jsonSprintBacklog.php');

$onlyRefresh = RequestHandler::getBoolean('onlyRefresh');
$oldColumn = RequestHandler::getValue('oldColumn');
$newColumn = RequestHandler::getValue('newColumn');
$onlyRefresh = ($oldColumn and $newColumn)?true:$onlyRefresh;
$arrayRefreshColumn=array($oldColumn=>$oldColumn, $newColumn=>$newColumn);

$hidebacklog=Parameter::getUserParameter('sprintBacklogHideBacklog');
$hideclosed = Parameter::getUserParameter ( "sprintBacklogHideClosed");
$fullwidthelement=Parameter::getUserParameter('sprintBacklogFullWidthElement');
$hidestatus=Parameter::getUserParameter('sprintBacklogHideStatus');
$hidesprint=Parameter::getUserParameter('sprintBacklogHideSprint');
$hideepic=Parameter::getUserParameter('sprintBacklogHideEpic');
$hideproduct=Parameter::getUserParameter('sprintBacklogHideProduct');
$hideresponsible=Parameter::getUserParameter('sprintBacklogHideResponsible');
$hidestorypointsandbusiness=Parameter::getUserParameter('sprintBacklogHideStoryPointsAndBusiness');
$hidehidetype=Parameter::getUserParameter('sprintBacklogHideType');
$hideprojectname=Parameter::getUserParameter('sprintBacklogHideProjectName');
$hidescrumpriority=Parameter::getUserParameter('sprintBacklogHideScrumPriority');
$showIdle = Parameter::getUserParameter("sprintBacklogShowIdle");
$showIdle = ($showIdle=='on' or $showIdle=='1')?true:false;
$orderBy = Parameter::getUserParameter('sprintBacklogOrderBy');

$orderBySql = "";
switch ($orderBy) {
  case 'id':
    $orderBySql = " us.id ";
    break;
  case 'name':
    $orderBySql = " us.name ";
    break;
  case 'scrumPriority':
    $orderBySql = " sp.sortOrder ";
    break;
  case 'storyPointsASC':
    $orderBySql = " us.storyPoints ASC ";
    break;
  case 'storyPointsDESC':
    $orderBySql = " us.storyPoints DESC ";
    break;
  case 'businessValueASC':
    $orderBySql = " us.businessValue ASC ";
    break;
  case 'businessValueDESC':
    $orderBySql = " us.businessValue DESC ";
    break;
  default:
    $orderBySql = " sp.sortOrder ";
}

$idSprint=(sessionValueExists('sprintBacklogIdSprint'))?pq_trim(getSessionValue('sprintBacklogIdSprint')):"";
$status = new Status();
$where = "forAgileScrum = '0'";
$statusList=SqlList::getListWithCrit('Status',$where,'id',null,true);
$idBacklogColumn = array_key_first($statusList);
$oldColumn = ($idBacklogColumn == $oldColumn)?'backlog':$oldColumn;
$newColumn = ($idBacklogColumn == $newColumn)?'backlog':$newColumn;
$refreshBacklog = (($hidebacklog == '' or $hidebacklog == 'on' or $hidebacklog == '1') and (!$onlyRefresh or $idBacklogColumn == $oldColumn or $idBacklogColumn == $newColumn)) ? true : false;
$onlyRefreshBacklog = ($oldColumn == 'backlog' and $newColumn == 'backlog') ? true : false;
$onlyRefreshClosed = ($oldColumn == 'closed' and $newColumn == 'closed') ? true : false;

if($onlyRefreshBacklog){
  $where = "forAgileScrum = '0' AND id IN (0, ".implode(',', $statusList).")";
}else if($onlyRefreshClosed){
  $where = "forAgileScrum = '1' AND setIdleStatus = '1'";
}else{
  $where = "forAgileScrum = '1' ".((!$hideclosed == 'off' or $hideclosed == '0')?"AND setIdleStatus = '0' ":"").(($onlyRefresh)?"AND id IN (0, ".implode(',', $arrayRefreshColumn).") ":"");
}
if($onlyRefreshBacklog){
  $arrayRefreshColumn = $statusList;
}else if ($onlyRefreshClosed){
  $where = "forAgileScrum = '1' AND setIdleStatus = '1'";
  $arrayRefreshColumn = SqlList::getListWithCrit('Status',$where,'id',null,true);
}

$agileStatusList = $status->getSqlElementsFromCriteria(null,null,$where,"sortOrder ASC");
$backlogStatus = array();
$jsonColumnList = array();

if($refreshBacklog or $onlyRefreshBacklog){
  $jsonColumnList[$idBacklogColumn]['id'] = $idBacklogColumn;
  $jsonColumnList[$idBacklogColumn]['type'] = 'Status';
  $jsonColumnList[$idBacklogColumn]['itemlist'] = array();
  $jsonColumnList[$idBacklogColumn]['fullwidthelement']=$fullwidthelement;
  $jsonColumnList[$idBacklogColumn]['hidestatus']=$hidestatus;
  $jsonColumnList[$idBacklogColumn]['hidesprint']=$hidesprint;
  $jsonColumnList[$idBacklogColumn]['hideepic']=$hideepic;
  $jsonColumnList[$idBacklogColumn]['hideproduct']=$hideproduct;
  $jsonColumnList[$idBacklogColumn]['hideresponsible']=$hideresponsible;
  $jsonColumnList[$idBacklogColumn]['hidestorypointsandbusiness']=$hidestorypointsandbusiness;
  $jsonColumnList[$idBacklogColumn]['hidehidetype']=$hidehidetype;
  $jsonColumnList[$idBacklogColumn]['hideprojectname']=$hideprojectname;
  $jsonColumnList[$idBacklogColumn]['hidescrumpriority']=$hidescrumpriority;
}

foreach ($agileStatusList as $agileStatus){
  $backlogStatus[$agileStatus->id]=$agileStatus->id;
  if(!isset($jsonColumnList[$agileStatus->id])){
    $jsonColumnList[$agileStatus->id]=array();
  }
  $jsonColumnList[$agileStatus->id]['id'] = $agileStatus->id;
  $jsonColumnList[$agileStatus->id]['type'] = 'Status';
  $jsonColumnList[$agileStatus->id]['itemlist'] = array();
  $jsonColumnList[$agileStatus->id]['fullwidthelement']=$fullwidthelement;
  $jsonColumnList[$agileStatus->id]['hidestatus']=$hidestatus;
  $jsonColumnList[$agileStatus->id]['hidesprint']=$hidesprint;
  $jsonColumnList[$agileStatus->id]['hideepic']=$hideepic;
  $jsonColumnList[$agileStatus->id]['hideproduct']=$hideproduct;
  $jsonColumnList[$agileStatus->id]['hideresponsible']=$hideresponsible;
  $jsonColumnList[$agileStatus->id]['hidestorypointsandbusiness']=$hidestorypointsandbusiness;
  $jsonColumnList[$agileStatus->id]['hidehidetype']=$hidehidetype;
  $jsonColumnList[$agileStatus->id]['hideprojectname']=$hideprojectname;
  $jsonColumnList[$agileStatus->id]['hidescrumpriority']=$hidescrumpriority;
}

$us   = new UserStory();
$ust  = new UserStoryType();
$spt  = new Sprint();
$ep   = new Epic();
$st   = new Status();
$sp   = new ScrumPriority();
$p    = new Project();
$aff  = new Affectable();
$tpv  = new Version();
$n    = new Note();

// ====== SELECT ======
$querySelect  = " us.id                     AS iduserstory, ";
$querySelect .= " us.name                   AS name, ";
$querySelect .= " us.idProject              AS idproject, ";
$querySelect .= " us.idStatus               AS idstatus, ";
$querySelect .= " us.idSprint               AS idsprint, ";
$querySelect .= " us.idEpic                 AS idepic, ";
$querySelect .= " us.idUserStoryType        AS iduserstorytype, ";
$querySelect .= " us.idScrumPriority        AS idscrumpriority, ";
$querySelect .= " us.idResource             AS idresource, ";
$querySelect .= " us.storyPoints            AS storypoints, ";
$querySelect .= " us.businessValue          AS businessvalue, ";
$querySelect .= " us.idVersion              AS idtargetproductversion, ";
$querySelect .= " us.description            AS description, ";
$querySelect .= " ust.code                  AS typecode, ";
$querySelect .= " ust.name                  AS typename, ";
$querySelect .= " st.name                   AS statusname, ";
$querySelect .= " st.color                  AS statuscolor, ";
$querySelect .= " spt.name                  AS sprintname, ";
$querySelect .= " e.name                    AS epicname, ";
$querySelect .= " sp.name                   AS scrumpriorityname, ";
$querySelect .= " sp.color                  AS scrumprioritycolor, ";
$querySelect .= " sp.sortOrder              AS scrumprioritysortorder, ";
$querySelect .= " p.name                    AS projectname, ";
$querySelect .= " p.color                   AS projectcolor, ";
$querySelect .= " aff.fullName              AS resourcename, ";
$querySelect .= " tpv.name                  AS targetproductversionname, ";
$querySelect .= " COUNT(n.id)               AS notecount ";

// ====== FROM / JOIN ======
$queryFrom  = $us->getDatabaseTableName() ." us ";
$queryFrom .= " LEFT JOIN ".$ust->getDatabaseTableName()." ust ON ust.id = us.idUserStoryType ";
$queryFrom .= " LEFT JOIN ".$st->getDatabaseTableName()." st ON st.id = us.idStatus ";
$queryFrom .= " LEFT JOIN ".$spt->getDatabaseTableName()." spt ON spt.id = us.idSprint ";
$queryFrom .= " LEFT JOIN ".$ep->getDatabaseTableName()." e ON e.id = us.idEpic ";
$queryFrom .= " LEFT JOIN ".$sp->getDatabaseTableName()." sp ON sp.id = us.idScrumPriority ";
$queryFrom .= " LEFT JOIN ".$p->getDatabaseTableName()." p ON p.id = us.idProject ";
$queryFrom .= " LEFT JOIN ".$aff->getDatabaseTableName()." aff ON aff.id = us.idResource ";
$queryFrom .= " LEFT JOIN ".$tpv->getDatabaseTableName()." tpv ON tpv.id = us.idVersion ";
$queryFrom .= " LEFT JOIN ".$n->getDatabaseTableName()." n ON n.refType = 'UserStory' AND n.refId = us.id AND n.idle = '0' ";
                                
// ====== WHERE ======
$queryWhere = "us.idProject IN ".getVisibleProjectsList().(($onlyRefresh)?" AND us.idStatus IN (0, ".implode(',', $arrayRefreshColumn).") ":" ");
$queryWhere  .= (!$showIdle) ? " AND us.idle = '0' " : " ";
if ($idSprint) {
  $queryWhere .= "AND ( us.idSprint = ".Sql::fmtId($idSprint).' )';
}
$queryWhere .= (($hidebacklog == 'off' or $hidebacklog == '0')?"AND us.idStatus NOT IN (0, ".implode(',', $statusList).")":"");
$queryWhere .= (($hideclosed == 'off' or $hideclosed == '0' or $hideclosed == '')?" AND st.setIdleStatus != '1' ":" ");

// ====== GROUP BY ======
$queryGroupBy  = " us.id, us.name, us.idProject, us.idStatus, us.idSprint, us.idEpic, us.idUserStoryType, ";
$queryGroupBy .= " us.idResource, us.storyPoints, us.businessValue, ";
$queryGroupBy .= " us.idVersion, us.description, ";
$queryGroupBy .= " ust.code, ust.name, ";
$queryGroupBy .= " st.name, st.color, ";
$queryGroupBy .= " spt.name, e.name, ";
$queryGroupBy .= " sp.name, sp.color, sp.sortOrder, ";
$queryGroupBy .= " p.name, p.color, ";
$queryGroupBy .= " aff.fullName, ";
$queryGroupBy .= " tpv.name ";

// ====== ORDER BY ======
$queryOrderBy  = (($orderBySql)?" $orderBySql, ":"")." sp.sortOrder, us.idStatus, us.idUserStoryType, us.id ";

// ====== REQUÊTE FINALE ======
$query  = "SELECT ".$querySelect
. " FROM ".$queryFrom
. " WHERE ".$queryWhere
. " GROUP BY ".$queryGroupBy
. " ORDER BY ".$queryOrderBy;

$result = Sql::query($query);

// ======== JSON ARRAY =========
$jsonItemList = array();
while ($line = Sql::fetchLine($result)) {
  $key = 'Status_'.$line['idstatus'].'_UserStory_'.$line['iduserstory'];
  
  $jsonItemList[$key] = array();
  
  $jsonItemList[$key]['id']        = $key;
  $jsonItemList[$key]['dndtype']   = 'column'.$line['idstatus'];
  $jsonItemList[$key]['name']      = htmlEncode(pq_htmlspecialchars($line['name']));
  $jsonItemList[$key]['reftype']   = 'UserStory';
  $jsonItemList[$key]['iconclass'] = 'UserStory';
  $jsonItemList[$key]['refid']     = $line['iduserstory'];
  $jsonItemList[$key]['idtype']    = $line['iduserstorytype'];
  
  $jsonItemList[$key]['storypoints']   = intval($line['storypoints']);
  $jsonItemList[$key]['businessvalue'] = intval($line['businessvalue']);
  
  // type
  $typename = $line['typecode'];
  if (!$typename) {
    $typename = pq_substr(ucfirst($line['typename']), 0, 3);
  }
  $jsonItemList[$key]['typename'] = htmlEncode(pq_htmlspecialchars($typename));
  
  // projet
  $jsonItemList[$key]['idproject']    = $line['idproject'];
  $jsonItemList[$key]['projectname']  = htmlEncode(pq_htmlspecialchars($line['projectname']));
  $jsonItemList[$key]['projectcolor'] =
  $line['projectcolor'] ? $line['projectcolor'] : '#777777';
  
  // statut
  $jsonItemList[$key]['idstatus']    = $line['idstatus'];
  $jsonItemList[$key]['statusname']  = htmlEncode(pq_htmlspecialchars($line['statusname']));
  $jsonItemList[$key]['statuscolor'] = $line['statuscolor'];
  
  // scrum priority
  $jsonItemList[$key]['idscrumpriority']    = $line['idscrumpriority'];
  $jsonItemList[$key]['scrumpriorityname']  = htmlEncode(pq_htmlspecialchars($line['scrumpriorityname']));
  $jsonItemList[$key]['scrumprioritycolor'] = $line['scrumprioritycolor'];
  $jsonItemList[$key]['scrumprioritysortorder'] = $line['scrumprioritysortorder'];
  
  // responsable
  $jsonItemList[$key]['idresource']  = $line['idresource'];
  if ($line['idresource']) {
    $file     = Affectable::getThumbUrl('Affectable', $line['idresource'], 32);
    $username = pq_htmlspecialchars($line['resourcename']);
    
    if (pq_substr($file, 0, 6) == 'letter') {
      $isfile        = false;
      $responsibleicon = pq_strtoupper(pq_mb_substr($username, 0, 1, 'UTF-8'));
    } else {
      $isfile        = true;
      $responsibleicon = $file;
    }
    
    $usernametitle = $username.'<br/><span style= font-size:80% ><i>('.i18n('colResponsible').')</i></span>';
    
    $jsonItemList[$key]['responsible'] = array(
        'isfile'    => $isfile,
        'file'      => htmlEncode($responsibleicon),
        'name'      => htmlEncode($username),
        'nametitle' => htmlEncode($usernametitle)
    );
  } else {
    $jsonItemList[$key]['responsible'] = '';
  }
  
  // sprint id & name
  $jsonItemList[$key]['idsprint']   = $line['idsprint'];
  $jsonItemList[$key]['sprintname'] = $line['sprintname'];
  
  // epic id & name
  $jsonItemList[$key]['idepic']   = $line['idepic'];
  $jsonItemList[$key]['epicname'] = $line['epicname'];
  
  // version produit cible
  $jsonItemList[$key]['idtargetproductversion']   = $line['idtargetproductversion'];
  $jsonItemList[$key]['targetproductversionname'] = $line['targetproductversionname'];
  
  // description
  $description = $line['description'];
  if (!$description) {
    $description = "<div style='font-style:italic; color:#CDCADB;'>".i18n('kanbanNoDescription')."</div>";
  }
  $description = pq_str_replace(
      '<img ',
      '<img style="max-width:100%" onclick="showImage(\'Note\',this.src,\' \');" ',
      $description
      );
  $jsonItemList[$key]['description'] = htmlEncode(pq_htmlspecialchars($description));
  
  // nombre de notes
  $jsonItemList[$key]['notebadge'] = ($line['notecount'] > 0)?$line['notecount']:'';
  
  if(in_array($line['idstatus'], $backlogStatus)){
    $jsonColumnList[$line['idstatus']]['itemlist'][]=$jsonItemList[$key];
  }else if(!in_array($line['idstatus'], $backlogStatus) and ($refreshBacklog or $onlyRefreshBacklog)){
    $jsonColumnList[$idBacklogColumn]['itemlist'][]=$jsonItemList[$key];
  }
}

// ========== JSON FORMATTER ===========
$nbColumn=0;
echo '{"identifier":"id",' ;
echo ' "items":[';
foreach ($jsonColumnList as $column) {
  echo (++$nbColumn>1)?',':'';
  echo  '{';
  $nbFields=0;
  foreach ($column as $id=>$val){
    if ($val===null) {$val=" ";}
    if ($val=="") {$val=" ";}
    echo (++$nbFields>1)?',':'';
    if (pq_strpos($id, 'name')) {
      $val=htmlEncode(htmlEncodeJson($val));
    } else if(is_array($val)){
      $val=json_encode($val);
    } else {
      $val=htmlEncodeJson($val);
    }
    if($id=="itemlist"){
      echo '"' . htmlEncode($id) . '": ' . $val;
    }else{
      echo '"' . htmlEncode($id) . '":"' . $val . '"';
    }
  }
  echo  '}';
}
echo ' ] }';

?>