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
scriptLog('   ->/tool/jsonProductBacklog.php');

$onlyRefresh = RequestHandler::getBoolean('onlyRefresh');
$oldColumn = RequestHandler::getValue('oldColumn');
$newColumn = RequestHandler::getValue('newColumn');
$onlyRefresh = ($oldColumn and $newColumn)?true:$onlyRefresh;
$arrayRefreshColumn=array($oldColumn=>$oldColumn, $newColumn=>$newColumn);

$hidebacklog=Parameter::getUserParameter('productBacklogHideBacklog');
$fullwidthelement=Parameter::getUserParameter('productBacklogFullWidthElement');
$hideEpicItem=Parameter::getUserParameter('productBacklogHideEpicItem');
$hidestatus=Parameter::getUserParameter('productBacklogHideStatus');
$hidesprint=Parameter::getUserParameter('productBacklogHideSprint');
$hideepic=Parameter::getUserParameter('productBacklogHideEpic');
$hideproduct=Parameter::getUserParameter('productBacklogHideProduct');
$hideresponsible=Parameter::getUserParameter('productBacklogHideResponsible');
$hidestorypointsandbusiness=Parameter::getUserParameter('productBacklogHideStoryPointsAndBusiness');
$hidehidetype=Parameter::getUserParameter('productBacklogHideType');
$hideprojectname=Parameter::getUserParameter('productBacklogHideProjectName');
$hidescrumpriority=Parameter::getUserParameter('productBacklogHideScrumPriority');
$showIdle = Parameter::getUserParameter("productBacklogShowIdle");
$showIdle = ($showIdle=='on' or $showIdle=='1')?true:false;
$orderBy = Parameter::getUserParameter('productBacklogOrderBy');

$orderBySql = "";
switch ($orderBy) {
  case 'id':
    $orderBySql = " iditem ";
    break;
  case 'name':
    $orderBySql = " name ";
    break;
  case 'scrumPriority':
    $orderBySql = " scrumprioritysortorder ";
    break;
  case 'storyPointsASC':
    $orderBySql = " storypoints ASC ";
    break;
  case 'storyPointsDESC':
    $orderBySql = " storypoints DESC ";
    break;
  case 'businessValueASC':
    $orderBySql = " businessvalue ASC ";
    break;
  case 'businessValueDESC':
    $orderBySql = " businessvalue DESC ";
    break;
  default:
    $orderBySql = " scrumprioritysortorder ";
}

$idBacklogColumn = 0;
$refreshBacklog = (($hidebacklog == '' or $hidebacklog == 'on' or $hidebacklog == '1') and (!$onlyRefresh or $idBacklogColumn == $oldColumn or $idBacklogColumn == $newColumn or $oldColumn == 'backlog')) ? true : false;
$onlyRefreshBacklog = (($oldColumn == 'backlog' and $newColumn == 'backlog')) ? true : false;

$sprint = new Sprint();
$sprintList = array();
if(!$onlyRefreshBacklog){
  $where = "idle = 0 and idProject in ".getVisibleProjectsList();
  if($onlyRefresh){
    $where .= " AND id IN (0, ".implode(',', $arrayRefreshColumn).") ".(($refreshBacklog)?" OR id IS NULL":"");
  }
}else{
  $where = "idle = 0 and idProject in ".getVisibleProjectsList();
}
$sprintList = $sprint->getSqlElementsFromCriteria(null, null, $where);

$backlogSprint = array();
$jsonColumnList = array();

if($refreshBacklog or $onlyRefreshBacklog){
  $jsonColumnList[$idBacklogColumn]['id'] = $idBacklogColumn;
  $jsonColumnList[$idBacklogColumn]['type'] = 'Sprint';
  $jsonColumnList[$idBacklogColumn]['itemlist'] = array();
  $jsonColumnList[$idBacklogColumn]['fullwidthelement']=$fullwidthelement;
  $jsonColumnList[$idBacklogColumn]['hideepicitem']=$hideEpicItem;
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

foreach ($sprintList as $sprint){
  $backlogSprint[$sprint->id]=$sprint->id;
  if(!$onlyRefreshBacklog){
    if(!isset($jsonColumnList[$sprint->id])){
      $jsonColumnList[$sprint->id]=array();
    }
    $jsonColumnList[$sprint->id]['id'] = $sprint->id;
    $jsonColumnList[$sprint->id]['type'] = 'Sprint';
    $jsonColumnList[$sprint->id]['itemlist'] = array();
    $jsonColumnList[$sprint->id]['fullwidthelement']=$fullwidthelement;
    $jsonColumnList[$sprint->id]['hideepicitem']=$hideEpicItem;
    $jsonColumnList[$sprint->id]['hidestatus']=$hidestatus;
    $jsonColumnList[$sprint->id]['hidesprint']=$hidesprint;
    $jsonColumnList[$sprint->id]['hideepic']=$hideepic;
    $jsonColumnList[$sprint->id]['hideproduct']=$hideproduct;
    $jsonColumnList[$sprint->id]['hideresponsible']=$hideresponsible;
    $jsonColumnList[$sprint->id]['hidestorypointsandbusiness']=$hidestorypointsandbusiness;
    $jsonColumnList[$sprint->id]['hidehidetype']=$hidehidetype;
    $jsonColumnList[$sprint->id]['hideprojectname']=$hideprojectname;
    $jsonColumnList[$sprint->id]['hidescrumpriority']=$hidescrumpriority;
  }
}

$us   = new UserStory();
$ep   = new Epic();
$ust  = new UserStoryType();
$et   = new EpicType();
$st   = new Status();
$spt  = new Sprint();
$sp   = new ScrumPriority();
$p    = new Project();
$aff  = new Affectable();
$tpv  = new Version();
$n    = new Note();

// ====== SELECT EPIC ======
$querySelectUS  = " us.idSprint               AS idsprint, ";
$querySelectUS .= " us.id                     AS iditem, ";
$querySelectUS .= " us.name                   AS name, ";
$querySelectUS .= " us.idProject              AS idproject, ";
$querySelectUS .= " us.idStatus               AS idstatus, ";
$querySelectUS .= " us.idEpic                 AS idepic, ";
$querySelectUS .= " us.idUserStoryType        AS idtype, ";
$querySelectUS .= " us.idScrumPriority        AS idscrumpriority, ";
$querySelectUS .= " us.idResource             AS idresource, ";
$querySelectUS .= " us.storyPoints            AS storypoints, ";
$querySelectUS .= " us.businessValue          AS businessvalue, ";
$querySelectUS .= " us.idVersion              AS idtargetproductversion, ";
$querySelectUS .= " us.description            AS description, ";
$querySelectUS .= " 'UserStory'               AS reftype, ";
$querySelectUS .= " ust.code                  AS typecode, ";
$querySelectUS .= " ust.name                  AS typename, ";
$querySelectUS .= " st.name                   AS statusname, ";
$querySelectUS .= " st.color                  AS statuscolor, ";
$querySelectUS .= " spt.name                  AS sprintname, ";
$querySelectUS .= " e.name                    AS epicname, ";
$querySelectUS .= " sp.name                   AS scrumpriorityname, ";
$querySelectUS .= " sp.color                  AS scrumprioritycolor, ";
$querySelectUS .= " sp.sortOrder              AS scrumprioritysortorder, ";
$querySelectUS .= " p.name                    AS projectname, ";
$querySelectUS .= " p.color                   AS projectcolor, ";
$querySelectUS .= " aff.fullName              AS resourcename, ";
$querySelectUS .= " tpv.name                  AS targetproductversionname, ";
$querySelectUS .= " COUNT(n.id)               AS notecount ";

// ====== FROM USER STORY ======
$queryFromUS  = $us->getDatabaseTableName() ." us ";
$queryFromUS .= " LEFT JOIN ".$ust->getDatabaseTableName()." ust ON ust.id = us.idUserStoryType ";
$queryFromUS .= " LEFT JOIN ".$st->getDatabaseTableName()." st ON st.id = us.idStatus ";
$queryFromUS .= " LEFT JOIN ".$spt->getDatabaseTableName()." spt ON spt.id = us.idSprint ";
$queryFromUS .= " LEFT JOIN ".$ep->getDatabaseTableName()." e ON e.id = us.idEpic ";
$queryFromUS .= " LEFT JOIN ".$sp->getDatabaseTableName()." sp ON sp.id = us.idScrumPriority ";
$queryFromUS .= " LEFT JOIN ".$p->getDatabaseTableName()." p ON p.id = us.idProject ";
$queryFromUS .= " LEFT JOIN ".$aff->getDatabaseTableName()." aff ON aff.id = us.idResource ";
$queryFromUS .= " LEFT JOIN ".$tpv->getDatabaseTableName()." tpv ON tpv.id = us.idVersion ";
$queryFromUS .= " LEFT JOIN ".$n->getDatabaseTableName()." n ON n.refType = 'UserStory' AND n.refId = us.id AND n.idle = '0' ";

// ====== WHERE USER STORY ======
$queryWhereUS = "us.idProject IN ".getVisibleProjectsList();
$queryWhereUS .= (!$showIdle) ? " AND us.idle = '0' " : " ";
if($onlyRefresh){
  if($onlyRefreshBacklog){
    $queryWhereUS .= " AND ( us.idSprint IS NULL OR us.idSprint NOT IN (0, ".implode(',', $backlogSprint).") )";
  }else{
    $queryWhereUS .= " AND (us.idSprint IN (0, ".implode(',', $arrayRefreshColumn).") ".(($refreshBacklog)?" OR us.idSprint IS NULL )":" )");
  }
}
$queryWhereUS .= (($hidebacklog == 'off' or $hidebacklog == '0')?" AND us.idSprint IS NOT NULL ":" ");

// ====== GROUP BY USER STORY ======
$queryGroupByUS  = " us.idSprint, us.idEpic, us.id, us.name, us.idProject, us.idStatus, us.idUserStoryType, ";
$queryGroupByUS .= " us.idResource, us.storyPoints, us.businessValue, ";
$queryGroupByUS .= " us.idVersion, us.description, ";
$queryGroupByUS .= " ust.code, ust.name, ";
$queryGroupByUS .= " st.name, st.color, ";
$queryGroupByUS .= " spt.name, e.name, ";
$queryGroupByUS .= " sp.name, sp.color, sp.sortOrder, ";
$queryGroupByUS .= " p.name, p.color, ";
$queryGroupByUS .= " aff.fullName, ";
$queryGroupByUS .= " tpv.name ";

// ====== USER STORY QUERY ======
$queryUS  = "SELECT ".$querySelectUS
. " FROM ".$queryFromUS
. " WHERE ".$queryWhereUS
. " GROUP BY ".$queryGroupByUS;

// ================ EPIC PART =========================================

$querySelectEpic  = " e.idSprint               AS idsprint, ";
$querySelectEpic .= " e.id                     AS iditem, ";
$querySelectEpic .= " e.name                   AS name, ";
$querySelectEpic .= " e.idProject              AS idproject, ";
$querySelectEpic .= " e.idStatus               AS idstatus, ";
$querySelectEpic .= " NULL                     AS idepic, ";
$querySelectEpic .= " e.idEpicType             AS idtype, ";
$querySelectEpic .= " NULL                     AS idscrumpriority, ";
$querySelectEpic .= " NULL                     AS idresource, ";
$querySelectEpic .= " e.storyPoints            AS storypoints, ";
$querySelectEpic .= " e.businessValue          AS businessvalue, ";
$querySelectEpic .= " NULL                     AS idtargetproductversion, ";
$querySelectEpic .= " e.description            AS description, ";
$querySelectEpic .= " 'Epic'                   AS reftype, ";
$querySelectEpic .= " et.code                  AS typecode, ";
$querySelectEpic .= " et.name                  AS typename, ";
$querySelectEpic .= " st.name                  AS statusname, ";
$querySelectEpic .= " st.color                 AS statuscolor, ";
$querySelectEpic .= " spt.name                 AS sprintname, ";
$querySelectEpic .= " NULL                     AS epicname, ";
$querySelectEpic .= " NULL                     AS scrumpriorityname, ";
$querySelectEpic .= " NULL                     AS scrumprioritycolor, ";
$querySelectEpic .= " NULL                     AS scrumprioritysortorder, ";
$querySelectEpic .= " p.name                   AS projectname, ";
$querySelectEpic .= " p.color                  AS projectcolor, ";
$querySelectEpic .= " NULL                     AS resourcename, ";
$querySelectEpic .= " NULL                     AS targetproductversionname, ";
$querySelectEpic .= " 0                        AS notecount ";

$queryFromEpic  = $ep->getDatabaseTableName()." e ";
$queryFromEpic .= " LEFT JOIN ".$us->getDatabaseTableName()." us2 ON us2.idEpic = e.id AND us2.idle = '0' ";
$queryFromEpic .= " LEFT JOIN ".$st->getDatabaseTableName()." st ON st.id = e.idStatus ";
$queryFromEpic .= " LEFT JOIN ".$spt->getDatabaseTableName()." spt ON spt.id = e.idSprint ";
$queryFromEpic .= " LEFT JOIN ".$p->getDatabaseTableName()." p ON p.id = e.idProject ";
$queryFromEpic .= " LEFT JOIN ".$et->getDatabaseTableName()." et ON et.id = e.idEpicType ";

// WHERE EPIC
$queryWhereEpic  = "e.idProject IN ".getVisibleProjectsList();
$queryWhereEpic .= (!$showIdle) ? " AND e.idle = '0' " : " ";
if($onlyRefresh){
  if($onlyRefreshBacklog){
    $queryWhereEpic .= " AND ( e.idSprint IS NULL OR e.idSprint NOT IN (0, ".implode(',', $backlogSprint).") ) ";
  }else{
    $queryWhereEpic .= " AND ( e.idSprint IN (0, ".implode(',', $arrayRefreshColumn).") ".(($refreshBacklog)?" OR e.idSprint IS NULL )":" )");
  }
}
$queryWhereEpic .= (($hidebacklog == 'off' or $hidebacklog == '0')?" AND e.idSprint IS NOT NULL ":" ");

// GROUP BY EPIC
$queryGroupByEpic  = " e.idSprint, e.id, e.name, e.idProject, e.idStatus, e.idEpicType, ";
$queryGroupByEpic .= " e.description, ";
$queryGroupByEpic .= " et.code, et.name, ";
$queryGroupByEpic .= " st.name, st.color, ";
$queryGroupByEpic .= " spt.name, ";
$queryGroupByEpic .= " p.name, p.color";

// EPIC QUERY
$queryEpic  = "SELECT ".$querySelectEpic
. " FROM ".$queryFromEpic
. " WHERE ".$queryWhereEpic
. " GROUP BY ".$queryGroupByEpic;

// ====================================================================
// ================== UNION DES DEUX QUERIES ==========================
// ====================================================================

$hideEpicItemBool = ($hideEpicItem == 'off' or $hideEpicItem == '0') ? true : false;
if ($hideEpicItemBool) {
  $queryFinal = " (".$queryUS.") ORDER BY ".(($orderBySql)?" $orderBySql, ":"")." projectname, idstatus, idtype, iditem";
} else {
  $queryFinal = " (".$queryUS.") UNION ALL (".$queryEpic.") ORDER BY ".(($orderBySql)?" $orderBySql, ":"")." projectname, idstatus, idtype, iditem";
}
$result = Sql::query($queryFinal);

// ======== JSON ARRAY =========
$jsonItemList = array();
while ($line = Sql::fetchLine($result)) {
  $reftype = $line['reftype'];
  $idSprint = ($line['idsprint'])?$line['idsprint']:'0';
  $key = 'Sprint_'. $idSprint . '_'.$reftype . '_' . $line['iditem'];
  
  $jsonItemList[$key] = array();
  
  $jsonItemList[$key]['id']        = $key;
  $jsonItemList[$key]['dndtype']   = 'column'.$idSprint;
  $jsonItemList[$key]['name']      = htmlEncode(pq_htmlspecialchars($line['name']));
  $jsonItemList[$key]['reftype']   = $reftype;
  $jsonItemList[$key]['iconclass'] = $reftype;
  $jsonItemList[$key]['refid']     = $line['iditem'];
  $jsonItemList[$key]['idtype']    = $line['idtype'];
  
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
      "<img ",
      "<img style=\"max-width:100%\" onclick=\"showImage('Note\\',this.src,\\' ');\" ",
      $description
      );
  $jsonItemList[$key]['description'] = htmlEncode(pq_htmlspecialchars($description));
  
  // nombre de notes
  $jsonItemList[$key]['notebadge'] = ($line['notecount'] > 0)?$line['notecount']:'';
  
  if($line['idsprint'] and in_array($line['idsprint'], $backlogSprint)){
    $jsonColumnList[$line['idsprint']]['itemlist'][]=$jsonItemList[$key];
  }else if($refreshBacklog or $onlyRefreshBacklog){
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