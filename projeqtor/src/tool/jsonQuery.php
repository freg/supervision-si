<?PHP
/**
 * * COPYRIGHT NOTICE *********************************************************
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
 * FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 *
 * ** DO NOT REMOVE THIS NOTICE ***********************************************
 */

/**
 * ===========================================================================
 * Get the list of objects, in Json format, to display the grid list
 */
require_once "../tool/projeqtor.php";
session_write_close();
require_once "../tool/formatter.php";
require_once "../tool/jsonFunctions.php";
include_once "../report/headerFunctions.php";
scriptLog('   ->/tool/jsonQuery.php');
global $context;
$context='jsonQuery';
$objectClass=$_REQUEST['objectClass'];
Security::checkValidClass($objectClass);
$traceHack=true;
if (getSessionValue('directAccessClass')==$objectClass) {
  $traceHack=false;
} else if (getSessionValue('directAccessClass')) {
  unsetSessionValue('directAccessClass');
}
Security::checkValidAccessForUser(null, 'read', $objectClass, null, $traceHack);

$showThumb=Parameter::getUserParameter('paramShowThumbList');
if ($showThumb=='NO') {
  $showThumb=false;
} else {
  $showThumb=true;
}
$getWorkUnit=false;
$hiddenFields=array();
if (isset($_REQUEST['hiddenFields'])) {
  $hiddens=pq_explode(';', $_REQUEST['hiddenFields']);
  foreach ($hiddens as $hidden) {
    if (pq_trim($hidden)) {
      $hiddenFields[$hidden]=$hidden;
    }
  }
}
$print=false;
if (pq_array_key_exists('print', $_REQUEST)) {
  $print=true;
  include_once ('../tool/formatter.php');
}
$comboDetail=false;
if (pq_array_key_exists('comboDetail', $_REQUEST)) {
  $comboDetail=true;
}
$showAllProjects=false;
if (RequestHandler::isCodeSet('showAllProjects') and RequestHandler::getBoolean('showAllProjects')==true) {
  $showAllProjects=true;
}
$objectProject=null;
if (RequestHandler::isCodeSet('objectProject') and RequestHandler::getId('objectProject')!='') {
  $objectProject=pq_trim(RequestHandler::getId('objectProject'));
}
//#11179
$planningWbsFilter=false;
$planningWbsSortable=null;
if (RequestHandler::isCodeSet('planningWbsFilter') and RequestHandler::getValue('planningWbsFilter')=='1') {
  $planningWbsFilter=true;
}
if (RequestHandler::isCodeSet('planningWbsSortable') and RequestHandler::getValue('planningWbsSortable')!='') {
  $planningWbsSortable=pq_trim(RequestHandler::getValue('planningWbsSortable'));
}

$quickSearch=false;
if (pq_array_key_exists('quickSearch', $_REQUEST)) {
  $quickSearch=Sql::fmtStr($_REQUEST['quickSearch']);
}
if (pq_array_key_exists('quickSearchQuick', $_REQUEST)) {
  $quickSearch=Sql::fmtStr($_REQUEST['quickSearchQuick']);
}
if (!isset($outMode)) {
  $outMode="";
}
if (!isset($csvExportAll)) $csvExportAll=false;

if ($print&&$outMode=='csv') {
  global $contextForAttributes, $hideScope;
  $contextForAttributes='global';
  $hideScope='export';
}

$obj=new $objectClass();
$table=$obj->getDatabaseTableName();
$accessRightRead=securityGetAccessRight($obj->getMenuClass(), 'read');
$querySelect='';
$queryFrom=($objectClass=='GlobalView')?GlobalView::getTableNameQuery() . ' as ' . $table:$table;
$queryWhere='';
$queryOrderBy='';
$idTab=0;
$queryUOSelect='';
$queryUOFrom='';
$queryUOWhere='';

$res=array();

$idLayout=null;
$isReportList=false;
if (pq_array_key_exists('reportLayoutId', $_REQUEST)) {
  $idLayout=RequestHandler::getValue('reportLayoutId');
  $isReportList=true;
}
$layout=$obj->getLayout($idLayout, $isReportList);
$array=pq_explode('</th>', $layout);
// ====================== Build restriction clauses ================================================

// --- Quick search criteria (textual search in any text field, including notes)
if ($quickSearch) {
  $quickSearch=pq_str_replace(array('*', '.'), array('%', '_'), $quickSearch);
  $queryWhere.=($queryWhere=='')?'':' and ';
  $queryWhere.="( 1=2 ";
  $note=new Note();
  $noteTable=$note->getDatabaseTableName();
  $quickSearchEncoded = htmlentities($quickSearch, ENT_QUOTES, 'UTF-8');
  $quickSearchEncoded = pq_str_replace(array('*', '.'), array('%', '_'), $quickSearchEncoded);
  foreach ($obj as $fld=>$val) {
    if ($fld=='id' or $fld=='objectId' or $fld=='objectClass' or $fld=='refType' or $fld=='refId') continue;
    if ($obj->getDataType($fld)=='varchar') {
      $queryWhere.=' or ' . $table . "." . $obj->getDatabaseColumnName($fld) . " " . ((Sql::isMysql())?'LIKE':'ILIKE') . " '%" . $quickSearch . "%'";
      $queryWhere .= ' or ' . $table . "." . $obj->getDatabaseColumnName($fld) ." " . ((Sql::isMysql())?'LIKE':'ILIKE') . " '%" . $quickSearchEncoded . "%'";
    }
  }
  
  if (is_numeric($quickSearch)) {
    $queryWhere.=' or ' . $table . ".id=" . $quickSearch . "";
  }
  $queryWhere.=" or exists ( select 'x' from $noteTable ";
  if ($objectClass=='GlobalView') {
    $queryWhere.=" where $noteTable.refId=$table.objectId ";
    $queryWhere.=" and $noteTable.refType=$table.objectClass ";
  } else {
    $queryWhere.=" where $noteTable.refId=$table.id ";
    $queryWhere.=" and $noteTable.refType=" . Sql::str($objectClass);
  }
  $queryWhere.=" and $noteTable.note " . ((Sql::isMysql())?'LIKE':'ILIKE') . " '%" . $quickSearch . "%' ) ";
  $queryWhere.=" )";
}

if ($planningWbsFilter and $planningWbsSortable and $objectClass=='Activity') {
  $queryWhere.=($queryWhere=='')?'':' and ';
  $queryWhere.=$table . ".id in (
    select pe.refId
    from planningelement pe
    where pe.refType='Activity'
    and pe.wbsSortable " . ((Sql::isMysql())?'LIKE':'ILIKE') . " " . Sql::str($planningWbsSortable . '%') . "
  )";
}

// --- Should idle projects be shown ?
$showIdleProjects=(!$comboDetail and sessionValueExists('projectSelectorShowIdle') and getSessionValue('projectSelectorShowIdle')==1)?1:0;
// --- "show idle checkbox is checked ?
if (!isset($showIdle)) $showIdle=false;
if ($objectClass=='Work') {
  $showIdle=true;
}
if (getSessionValue("listShowIdle$objectClass", 'off')=='on') $showIdle=true;
if (!$showIdle and !pq_array_key_exists('idle', $_REQUEST) and !$quickSearch) {
  $queryWhere.=($queryWhere=='')?'':' and ';
  $queryWhere.=$table . "." . $obj->getDatabaseColumnName('idle') . "=0";
} else {
  $showIdle=true;
}
// For versions, hide versions in service
$hideInService=Parameter::getUserParameter('hideInService');
// if (Parameter::getUserParameter('hideInService')=='true' and property_exists($obj, 'isEis') and ! $quickSearch) {
if (Parameter::getUserParameter('hideInService')=='true' and property_exists($obj, 'isEis')) {
  $queryWhere.=($queryWhere=='')?'':' and ';
  $queryWhere.=$table . "." . $obj->getDatabaseColumnName('isEis') . "=0";
} else {
  $showIdle=true;
}

// --- Direct filter on id (only used for printing, as direct filter is done on client side)
// if (pq_array_key_exists('listIdFilter',$_REQUEST) and ! $quickSearch) {
if (pq_array_key_exists('listIdFilter', $_REQUEST)) {
  $param=$_REQUEST['listIdFilter'];
  $param=strtr($param, "*?", "%_");
  $param=Sql::fmtStr($param);
  $queryWhere.=($queryWhere=='')?'':' and ';
  $queryWhere.=$table . "." . $obj->getDatabaseColumnName('id') . " like '%" . $param . "%'";
}
// --- Direct filter on name (only used for printing, as direct filter is done on client side)
// if (pq_array_key_exists('listNameFilter',$_REQUEST) and ! $quickSearch) {
if (pq_array_key_exists('listNameFilter', $_REQUEST)) {
  $param=$_REQUEST['listNameFilter'];
  $param=strtr($param, "*?", "%_");
  $param=Sql::fmtStr($param);
  $queryWhere.=($queryWhere=='')?'':' and ';
  if (get_class($obj)=='Affectation' or get_class($obj)=='Assignment') {
    $r=new Resource();
    $rTable=$r->getDatabaseTableName();
    $queryWhere.=$table . ".idResource in (select id from $rTable where fullName " . ((Sql::isMysql())?'LIKE':'ILIKE') . " '%" . $param . "%' )";
  } else {
    $queryWhere.=$table . "." . $obj->getDatabaseColumnName('name') . " " . ((Sql::isMysql())?'LIKE':'ILIKE') . " '%" . $param . "%'";
  }
}
// --- Direct filter on type
// if ( pq_array_key_exists('objectType',$_REQUEST) and ! $quickSearch) {
if (pq_array_key_exists('objectType', $_REQUEST)) {
  if (pq_trim($_REQUEST['objectType'])!='') {
    $queryWhere.=($queryWhere=='')?'':' and ';
    // MTY - LEAVE SYSTEM
    if ($objectClass=="EmployeeLeaveEarned") {
      $queryWhere.=$table . "." . $obj->getDatabaseColumnName('idLeaveType') . "=" . Sql::str($_REQUEST['objectType']);
    } else {
      $queryWhere.=$table . "." . $obj->getDatabaseColumnName('id' . $objectClass . 'Type') . "=" . Sql::str($_REQUEST['objectType']);
    }
    // MTY - LEAVE SYSTEM
  }
  // ADD - Activity type restriction by project - F.KARA #459
  if (pq_substr($objectClass, -4)=='Type' and $comboDetail) {
    $idProjectSelected=getSessionValue("idProjectSelectedForComboDetail");
    $restrictType=new RestrictType();
    $restrictTypeActivity=$restrictType->getSqlElementsFromCriteria(array('idProject'=>$idProjectSelected));
    $tabRestrictedTypeId=array();
    foreach ($restrictTypeActivity as $rest) {
      array_push($tabRestrictedTypeId, $rest->idType);
    }
    if (count($tabRestrictedTypeId)!=0) {
      $queryWhere.=' and type.id in ' . transformValueListIntoInClause($tabRestrictedTypeId);
    }
  }
  // END - Activity type restriction by project - F.KARA #459
}

// --- Report filter on Resource
// if ( pq_array_key_exists('objectResource',$_REQUEST) and ! $quickSearch) {
if (pq_array_key_exists('objectResource', $_REQUEST)) {
  $res=new Resource();
  $resourceTable=$res->getDatabaseTableName();
  if (pq_trim($_REQUEST['objectResource'])!='' and property_exists($objectClass, 'idResource')) {
    $queryWhere.=($queryWhere=='')?'':' and ';
    $queryWhere.=$table . ".idResource=" . Sql::str($_REQUEST['objectResource']);
  }
}

// --- Report filter on Organization
// if ( pq_array_key_exists('objectOrganization',$_REQUEST) and ! $quickSearch) {
if (pq_array_key_exists('objectOrganization', $_REQUEST)) {
  $objectOrganization=pq_trim($_REQUEST['objectOrganization']);
  if ($objectOrganization!='' and property_exists($objectClass, 'idOrganization')) {
    $queryWhere.=($queryWhere=='')?'':' and ';
    $queryWhere.=$table . ".idOrganization=" . Sql::str($objectOrganization);
  }
}

// --- Report filter on Team
// if ( pq_array_key_exists('objectTeam',$_REQUEST) and ! $quickSearch) {
if (pq_array_key_exists('objectTeam', $_REQUEST)) {
  $objectTeam=pq_trim($_REQUEST['objectTeam']);
  if ($objectTeam!='' and property_exists($objectClass, 'idTeam')) {
    $queryWhere.=($queryWhere=='')?'':' and ';
    $queryWhere.=$table . ".idTeam=" . Sql::str($objectTeam);
  }
}

// --- Direct filter on client
// if ( pq_array_key_exists('objectClient',$_REQUEST) and ! $quickSearch) {
if (pq_array_key_exists('objectClient', $_REQUEST)) {
  if (pq_trim($_REQUEST['objectClient'])!='' and property_exists($obj, 'idClient')) {
    $queryWhere.=($queryWhere=='')?'':' and ';
    $queryWhere.="(" . $table . "." . $obj->getDatabaseColumnName('idClient') . "=" . Sql::str($_REQUEST['objectClient']);
    if (property_exists($obj, '_OtherClient')) {
      $otherclient=new OtherClient();
      $queryWhere.=" or exists (select 'x' from " . $otherclient->getDatabaseTableName() . " other " . " where other.refType=" . Sql::str($objectClass) . " and other.refId=" . $table . ".id and other.idClient=" . Sql::fmtId(RequestHandler::getId('objectClient')) . ")";
    }
    $queryWhere.=")";
  }
}
// --- Direct filter on elementable
// if ( pq_array_key_exists('objectElementable',$_REQUEST) and ! $quickSearch) {
if (pq_array_key_exists('objectElementable', $_REQUEST)) {
  if (pq_trim($_REQUEST['objectElementable'])!='') {
    $elementable=null;
    if (property_exists($obj, 'idMailable')) $elementable='idMailable';
    else if (property_exists($obj, 'idIndicatorable')) $elementable='idIndicatorable';
    else if (property_exists($obj, 'idTextable')) $elementable='idTextable';
    else if (property_exists($obj, 'idChecklistable')) $elementable='idChecklistable';
    else if (property_exists($obj, 'idSituationable')) $elementable='idSituationable';
    if ($elementable) {
      $queryWhere.=($queryWhere=='')?'':' and ';
      $queryWhere.=$table . "." . $obj->getDatabaseColumnName($elementable) . "=" . Sql::str($_REQUEST['objectElementable']);
    }
  }
}
// ADD qCazelles - Filter by Status
// --- Direct filter on status
// if ( pq_array_key_exists('countStatus',$_REQUEST) and property_exists($obj, 'idStatus') and !$quickSearch) {
if (pq_array_key_exists('countStatus', $_REQUEST) and property_exists($obj, 'idStatus')) {
  $queryWhere.=($queryWhere=='')?'':' and ';
  $queryWhere.=$table . '.' . $obj->getDatabaseColumnName('idStatus') . ' in (0';
  for ($i=1; $i<=$_REQUEST['countStatus']; $i++) {
    if (pq_array_key_exists('objectStatus' . $i, $_REQUEST) and pq_trim($_REQUEST['objectStatus' . $i])!='') {
      $queryWhere.=', ' . Sql::str($_REQUEST['objectStatus' . $i]);
    }
  }
  $queryWhere.=')';
}
// END ADD qCazelles
// --- Direct filter on tags
// if ( pq_array_key_exists('countTags',$_REQUEST) and property_exists($obj, 'tags') and !$quickSearch)
if (pq_array_key_exists('countTags', $_REQUEST) and property_exists($obj, 'tags')) {
  $queryWhere.=($queryWhere=='')?'':' and ';
  $queryWhere.='( 1=0';
  for ($i=1; $i<=$_REQUEST['countTags']; $i++) {
    if (pq_array_key_exists('objectTags' . $i, $_REQUEST) and pq_trim($_REQUEST['objectTags' . $i])!='') {
      $tagName=SqlList::getNameFromId('Tag', $_REQUEST['objectTags' . $i], false);
      $queryWhere.=' or ' . $table . "." . $obj->getDatabaseColumnName('tags') . " " . ((Sql::isMysql())?'LIKE':'ILIKE') . " '%#" . $tagName . "#%'";
    }
  }
  $queryWhere.=' )';
}
// MTY - LEAVE SYSTEM
// Don't take the Leave Project if it's not visible for the connected user
if (isLeavesSystemActiv()) {
  if ($objectClass=='Project' and !Project::isProjectLeaveVisible()) {
    $queryWhere.=($queryWhere=='')?'':' and ';
    // $queryWhere.= $table . ".isLeaveMngProject = 0 ";
    $queryWhere.=$table . ".id <> " . Project::getLeaveProjectId();
  }
  // if ($objectClass=='Activity' and !Project::isProjectLeaveVisible()) {
  // $queryWhere.= ($queryWhere=='')?'':' and ';
  // $queryWhere.= $table . ".idProject !=".Project::getLeaveProjectId();
  // }
}
// MTY - LEAVE SYSTEM
// --- Restrict to allowed projects : for Projects list
if ($objectClass=='Project' and $accessRightRead!='ALL') {
  $accessRightRead='ALL';
  $queryWhere.=($queryWhere=='')?'':' and ';
  $queryWhere.='(' . $table . ".id in " . transformListIntoInClause(getSessionUser()->getVisibleProjects(!$showIdle));
  $queryWhere.=" or $table.codeType='TMP' "; // Templates projects are always visible in projects list
  $queryWhere.=')';
}

// --- Restrict to allowed project taking into account selected project : for all list that are project dependant
if (property_exists($obj, 'idProject') and sessionValueExists('project')) {
  // MTY - LEAVE SYSTEM
  // Don't take the Leave Project if it's not visible for the connected user
  if (isLeavesSystemActiv()) {
    if ($objectClass!='Project'&&!Project::isProjectLeaveVisible()&&Project::getLeaveProjectId()&&pq_trim(Project::getLeaveProjectId())) {
      $queryWhere.=($queryWhere=='')?'':' and ';
      $queryWhere.="($table.idProject <> " . Project::getLeaveProjectId() . " or $table.idProject is null)";
    }
  }
  // MTY - LEAVE SYSTEM
  if (((getSessionValue('project')!='*' and !$showAllProjects) or (getSessionValue('idFavoriteProjectList') and !$showAllProjects) or $objectProject)) {
    $queryWhere.=($queryWhere=='')?'':' and ';
    if ($objectClass=='Project') {
      $queryWhere.=$table . '.id in ' . getVisibleProjectsList(!$showIdleProjects, $objectProject);
    } else if ($objectClass=='Work') {
      $queryWhere.="1=1";
    } else if ($objectClass=='Document') {
      $app=new Approver();
      $appTable=$app->getDatabaseTableName();
      // Fix : do not systematically show documents where user is approver if project is selected
      // $queryWhere.= "(" . $table . ".idProject in " . getVisibleProjectsList(! $showIdleProjects) . " or " . $table . ".idProject is null or exists (select 'x' from $appTable app where app.refType='Document' and app.refId=$table.id and app.idAffectable=$user->id ))";
      $queryWhere.="(" . $table . ".idProject in " . getVisibleProjectsList(!$showIdleProjects, $objectProject) . ")";
    } else if ($obj->isAttributeSetToField('idProject', 'required')) {
      $queryWhere.=$table . ".idProject in " . getVisibleProjectsList(!$showIdleProjects, $objectProject);
    } else {
      $queryWhere.="($table.idProject in " . getVisibleProjectsList(!$showIdleProjects, $objectProject) . " or $table.idProject is null)";
    }
  }
}

// Gautier #itemTypeRestriction
if (Parameter::getGlobalParameter('hideItemTypeRestrictionOnProject')=='YES' and !$showAllProjects) {
  $lstGetClassList=Type::getClassList();
  $objType=$obj->getTypeClassName($objectClass);
  $lstGetClassList=array_flip($lstGetClassList);
  if (in_array($objType, $lstGetClassList)) {
    $objectClassRestrict=($objectClass=='TicketSimple')?'Ticket':$objectClass;
    $queryWhere.=($queryWhere)?' and ':'';
    $queryWhere.=$user->getItemTypeRestriction($obj, $objectClassRestrict, $user, $showIdle, $showIdleProjects);
  }
}
// --- Take into account restriction visibility clause depending on profile
if (($objectClass=='Version' or $objectClass=='Resource') and $comboDetail) {
  // No limit, although idProject exists
} else {
  $clause=getAccesRestrictionClause($objectClass, $table, $showIdleProjects);
  // gautier #1700
  if (pq_trim($clause) and $objectClass!="Work" and $objectClass!='GlobalView') {
    $queryWhere.=($queryWhere=='')?'(':' and (';
    $queryWhere.=$clause;
    if ($objectClass=='Project') {
      $queryWhere.=" or $table.codeType='TMP' "; // Templates projects are always visible in projects list
    } else if ($objectClass=='Document' and getSessionValue('project')=='*' or $showAllProjects and pq_strpos(getSessionValue('project'), ",")===null) {
      $app=new Approver();
      $appTable=$app->getDatabaseTableName();
      $queryWhere.="or exists (select 'x' from $appTable app where app.refType='Document' and app.refId=$table.id and app.idAffectable=$user->id )";
    }
    $queryWhere.=')';
  }
}
if ($objectClass=='Resource' or $objectClass=='ResourceTeam' or $objectClass=='ResourceMaterial' or $objectClass=='ResourceAllNoMaterial') {
  $scope=Affectable::getVisibilityScope('Screen');
  if ($scope!="all") {
    $queryWhere.=($queryWhere=='')?'':' and ';
    // ADD BY Marc TABARY - 2017-02-21 - RESOURCE VISIBILITY
    switch ($scope) {
      case 'subOrga' :
        $queryWhere.=" $table.idOrganization in (" . Organization::getUserOrganizationList() . ")";
        break;
      case 'orga' :
        if (!Organization::getUserOrganization()) {
          $queryWhere.="$table.idOrganization = -1 ";
        } else {
          ;
          $queryWhere.=" $table.idOrganization = " . Organization::getUserOrganization();
        }
        break;
      case 'team' :
        $aff=new Affectable(getSessionUser()->id, true);
        $queryWhere.=" $table.idTeam='$aff->idTeam'";
        break;
      default :
        break;
    }
  }
}

// ADD BY Marc TABARY - 2017-02-20 - ORGANIZATION VISIBILITY
if ($objectClass=='Organization') {
  $scope=Affectable::getOrganizationVisibilityScope('Screen');
  if ($scope!="all") {
    $queryWhere.=($queryWhere=='')?'':' and ';
    if ($scope=='subOrga') {
      // Can see organization and sub-organizations
      $queryWhere.=" $table.id in (" . Organization::getUserOrganizationList() . ")";
    } else if ($scope=='orga') {
      // Can see only organization
      $aff=new Affectable(getSessionUser()->id, true);
      $queryWhere.=" $table.id='$aff->idOrganization'";
    }
  }
}

// END ADD BY Marc TABARY - 2017-02-20 - ORGANIZATION VISIBILITY

// --- Apply systematic restriction criteria defined for the object class (for instance, for types, limit to corresponding type)
$crit=$obj->getDatabaseCriteria();
foreach ($crit as $col=>$val) {
  $queryWhere.=($queryWhere=='')?'':' and ';
  $queryWhere.=$obj->getDatabaseTableName() . '.' . $obj->getDatabaseColumnName($col) . "=" . Sql::str($val) . " ";
}

// --- If isPrivate existe, take into account privacy
if (property_exists($obj, 'isPrivate')) {
  $queryWhere.=($queryWhere=='')?'':' and ';
  $queryWhere.=SqlElement::getPrivacyClause($obj);
}
// --- When browsing Docments throught directory view, limit list of Documents to currently selected Directory
if ($objectClass=='Document') {
  if (sessionValueExists('Directory')) {
    $dirColumn=$obj->getDatabaseTableName() . '.' . $obj->getDatabaseColumnName('idDocumentDirectory');
    $queryWhere.=($queryWhere=='')?'':' and ';
    if (getSessionValue('currentScreen')=='DocumentExplorer') {
      // Document explorer : the documents of the selected directory, and only
      // those. Not recursive - a parent directory does not show what its
      // sub-directories hold.
      // The tree still says whether that directory may be seen at all : read
      // rights per directory and the "show closed" rule live there.
      require_once "../tool/documentExplorerTreeData.php";
      if (documentExplorerDirectoryIsVisible(getSessionValue('Directory'))) {
        $queryWhere.=$dirColumn . "=" . Sql::fmtId(getSessionValue('Directory')) . " ";
      } else {
        // Selected directory no longer visible : show nothing rather than everything.
        $queryWhere.=" 1=0 ";
      }
    } else {
      $queryWhere.=$dirColumn . "='" . getSessionValue('Directory') . "'";
    }
  }
}

// --- Apply sorting filers --------------------------------------------------------------
// --- 1) retrieve corresponding filter clauses depending on context
// $arrayFilter=($quickSearch)?array():jsonGetFilterArray($objectClass, $comboDetail, $idLayout);
$arrayFilter=jsonGetFilterArray($objectClass, $comboDetail, $idLayout);
// --- 2) sort from index checked in List Header (only used for printing, as direct filter is done on client side)
$sortIndex=null;
if ($print and $outMode!='csv') {
  if (pq_array_key_exists('sortIndex', $_REQUEST)) {
    $sortIndex=$_REQUEST['sortIndex']+1;
    $sortWay=(pq_array_key_exists('sortWay', $_REQUEST))?$_REQUEST['sortWay']:'asc';
    $nb=0;
    $numField=0;
    foreach ($array as $val) {
      $fld=htmlExtractArgument($val, 'field');
      if ($fld and $fld!="photo") {
        $numField+=1;
        if ($sortIndex and $sortIndex==$numField) {
          $queryOrderBy.=($queryOrderBy=='')?'':', ';
          // if (Sql::isPgsql()) $fld='"'.$fld.'"';
          if (property_exists($obj, $fld)) {
            $queryOrderBy.=" " . $obj->getDatabaseTableName() . "." . $fld . " " . $sortWay;
          } else if (property_exists($obj, $objectClass . 'PlanningElement') and property_exists($objectClass . 'PlanningElement', $fld)) {
            $queryOrderBy.=" " . pq_strtolower($objectClass) . "planningelement." . $fld . " " . $sortWay;
          } else if (property_exists($obj, 'WorkElement') and property_exists('WorkElement', $fld)) {
            $queryOrderBy.=" workelement." . $fld . " " . $sortWay;
          } else {
            $queryOrderBy.=" " . $fld . " " . $sortWay;
          }
        }
      }
    }
  }
}
// 3) sort from Filter Criteria
// if (! $quickSearch) {
jsonBuildSortCriteria($querySelect, $queryFrom, $queryWhere, $queryOrderBy, $idTab, $arrayFilter, $obj);
// }
// --- Rest of filter selection will be done later, after building select clause

// ====================== Build restriction clauses ================================================
// --- Build select clause, and eventualy extended From clause and Where clause
$numField=0;
$formatter=array();
$arrayWidth=array();
if ($outMode=='csv') {
  $obj=new $objectClass();
  $arrayDependantObjects=array('Document'=>array('_DocumentVersion'=>new DocumentVersion()));
  $arrayDep=array();
  if (isset($arrayDependantObjects[$objectClass])) {
    $arrayDep=$arrayDependantObjects[$objectClass];
  }
  $clause=$obj->buildSelectClause(false, $hiddenFields, $arrayDep);
  $querySelect.=($querySelect=='')?'':', ';
  $querySelect.=$clause['select'];
  // $queryFrom .= ($queryFrom=='')?'':', ';
  $queryFrom.=$clause['from'];
  if (!isset($hiddenFields['hyperlink'])) {
    $querySelect.=($querySelect=='')?'':', ';
    $querySelect.=$obj->getDatabaseTableName() . '.id as hyperlink';
  }
  if ($objectClass=='Assignment' and !isset($hiddenFields['itemName'])) {
    $querySelect.=($querySelect=='')?'':', ';
    $ass=new Assignment();
    $assTable=$ass->getDatabaseTableName();
    $queryRefTypes=sql::query("SELECT DISTINCT refType FROM $assTable");
    $refTypes=[];
    $isPgSql=Sql::isPgsql();
    foreach ($queryRefTypes as $row) {
      if ($isPgSql) {
        if (isset($row['reftype'])&&!in_array($row['reftype'], $refTypes)) {
          if (class_exists($row['reftype'])) $refTypes[]=$row['reftype'];
        }
      } else {
        if (isset($row['refType'])&&!in_array($row['refType'], $refTypes)) {
          if (class_exists($row['refType'])) $refTypes[]=$row['refType'];
        }
      }
    }
    $querySelect.=' CASE';
    foreach ($refTypes as $item) {
      $itemAlias=strtoupper(substr($item, 0, 2));
      $querySelect.=" WHEN $table.refType = '$item' THEN $itemAlias.name";
    }
    $querySelect.=' ELSE NULL END AS ' . ((Sql::isPgsql())?'"itemName"':'itemName');
    foreach ($refTypes as $item) {
      $itemObj=new $item();
      $itemTable=$itemObj->getDatabaseTableName();
      $itemAlias=strtoupper(substr($item, 0, 2));
      $queryFrom.=" LEFT JOIN $itemTable AS $itemAlias ON $table.refType = '$item' AND $table.refId = $itemAlias.id ";
    }
  }
  $arrayUORefName=array();
  $arrayUOFullName=array();
  if ($objectClass=='Activity' and !isset($hiddenFields['CatalogUO'])) {
    $getWorkUnit=true;
    $comp=new Complexity();
    $workU=new WorkUnit();
    $actWrkU=new ActivityWorkUnit();
    $idProj=(pq_strpos(getSessionValue('project'), ',')!==false)?pq_substr(getSessionValue('project'), 0, pq_strpos(getSessionValue('project'), ',')):getSessionValue('project');
    if ($idProj=='*') {
      $lstProject=pq_explode(', ', pq_substr(getVisibleProjectsList(), 1, (pq_strlen(getVisibleProjectsList())-2)));
      foreach ($lstProject as $id) {
        $project=new Project($id);
        if ($project->idCatalogUO) {
          $idProj=$id;
          break;
        }
      }
    }
    $proj=new Project($idProj);
    $lstCompl=$comp->getSqlElementsFromCriteria(array('idCatalogUO'=>$proj->idCatalogUO));
    $lstRef=$workU->getSqlElementsFromCriteria(array('idCatalogUO'=>$proj->idCatalogUO));
    $countRefSum=count($lstCompl)*count($lstRef);
    $clauseWhere=array();
    foreach ($lstRef as $ref) {
      foreach ($lstCompl as $comp) {
        $id=$ref->reference . '_' . $comp->name;
        $id=htmlentities($id, ENT_NOQUOTES, 'utf-8');
        $id=preg_replace('#&([A-za-z])(?:uml|circ|tilde|acute|grave|cedil|ring);#', '\1', $id);
        $id=preg_replace('#&([A-za-z]{2})(?:lig);#', '\1', $id);
        $id=preg_replace('#&[^;]+;#', '', $id);
        $id=pq_strtolower($id);
        $uoName=$ref->reference . ' - ' . $comp->name;
        // $id = pq_str_replace(array('"',"'",'#','&','$','~','!','/','\\',), ' ', $id);
        $id=preg_replace("/[^A-Za-z0-9 _]/", ' ', $id);
        if (!isset($arrayUORefName[$id])) {
          $arrayUORefName[$id]=$id;
          $arrayUOFullName[$id]=$uoName;
          $clauseWhere[$id]='(' . $actWrkU->getDatabaseTableName() . '.idComplexity = ' . $comp->id . ' and ' . $actWrkU->getDatabaseTableName() . '.idWorkUnit = ' . $ref->id . ')';
        }
      }
    }
    foreach ($clauseWhere as $id=>$wh) {
      $queryUOSelect.=', (select sum(' . $actWrkU->getDatabaseTableName() . '.quantity) from ' . $actWrkU->getDatabaseTableName() . ' where ' . $wh . ' and ' . $obj->getDatabaseTableName() . '.id = ' . $actWrkU->getDatabaseTableName() . '.refId and ' . $actWrkU->getDatabaseTableName() . '.refType = \'Activity\') as \'' . $arrayUORefName[$id] . '\'';
    }
  }
} else {

  $sumFld=Parameter::getUserParameter('listSumOnFilter' . $objectClass);
  $socSw=Parameter::getUserParameter('listSumOnFilterQuickSw' . $objectClass);
  if ($sumFld and $socSw=='on') {
    $from='';
    $format='';
    if (property_exists($objectClass, $sumFld)) {
      $from='';
    }
    if (property_exists($objectClass, 'WorkElement') and property_exists('WorkElement', $sumFld)) {
      $from='WorkElement';
      $format='workFormatter';
    } else if (property_exists($objectClass, $objectClass . 'PlanningElement') and property_exists($objectClass . 'PlanningElement', $sumFld)) {
      if (substr($sumFld, -8)=='Duration') {
        ;
        $from='PlanningElement';
        $format='workFormatter';
      } else {
        $from='PlanningElement';
        $format='workFormatter';
      }
    } else {
      if (substr($sumFld, -6)=="Amount") {
        $format="costFormatter";
        if (substr($sumFld, -11)=="AmountLocal") {
          $format="costFormatterLocal";
        }
      } else {
        $format="numericFormatter";
      }
    }
    $sumFieldInLayout=false;
    foreach ($array as $layoutColumn) {
      if (htmlExtractArgument($layoutColumn, 'field')==$sumFld) {
        $sumFieldInLayout=true;
        break;
      }
    }
    if (!$sumFieldInLayout) {
      $array[]='<th field="' . $sumFld . '" formatter="' . $format . '" from="' . $from . '">';
    }
  }

  // PBER #11085 - add wbsSortable to ensure correct sort
  $peName=$objectClass . 'PlanningElement';
  if ($objectClass=='PeriodicMeeting') $peName='MeetingPlanningElement';
  if (property_exists($obj, $peName)) {
    $array[]='<th field="wbsSortable" from="' . $peName . '">';
  }
  foreach ($array as $val) {
    // $sp=preg_split('field=', $val);
    // $sp=pq_explode('field=', $val);
    $fld=htmlExtractArgument($val, 'field');
    $isIdFieldName=(pq_substr($fld, 0, 4)=='name' and pq_strlen($fld)>4)?true:false;
    if ($isIdFieldName and property_exists($obj, $fld) and !property_exists($obj, 'id' . pq_substr($fld, 4))) $isIdFieldName=false;
    if ($fld) {
      $numField+=1;
      $formatter[$numField]=htmlExtractArgument($val, 'formatter');
      $from=htmlExtractArgument($val, 'from');
      $arrayWidth[$numField]=htmlExtractArgument($val, 'width');
      $querySelect.=($querySelect=='')?'':', ';
      if (pq_substr($formatter[$numField], 0, 5)=='thumb' and pq_substr($formatter[$numField], 0, 9)!='thumbName') {
        $querySelect.=pq_substr($formatter[$numField], 5) . ' as ' . $fld;
        ;
        continue;
      }
      if (pq_strlen($fld)>9 and pq_substr($fld, 0, 9)=="colorName") {
        $idTab+=1;
        // requested field are colorXXX and nameXXX => must fetch the from external table, using idXXX
        $externalClass=pq_substr($fld, 9);
        $externalObj=new $externalClass();
        $externalTable=$externalObj->getDatabaseTableName();
        $externalTableAlias='T' . $idTab;
        if (Sql::isPgsql()) {
          // $querySelect .= 'concat(';
          if (property_exists($externalObj, 'sortOrder')) {
            $querySelect.="LPAD(" . $externalTableAlias . '.' . $externalObj->getDatabaseColumnName('sortOrder') . "::text,5,'0')";
            $querySelect.=" || '#split#' ||";
          }
          $querySelect.=$externalTableAlias . '.' . $externalObj->getDatabaseColumnName('name');
          $querySelect.=" || '#split#' ||";
          $querySelect.="COALESCE(" . $externalTableAlias . '.' . $externalObj->getDatabaseColumnName('color') . ",'')";
          // $querySelect .= ') as "' . $fld .'"';
          if ($print) $querySelect.=' as ' . $fld;
          else $querySelect.=' as "' . $fld . '"';
        } else {
          $querySelect.='convert(';
          $querySelect.='concat(';
          if (property_exists($externalObj, 'sortOrder')) {
            $querySelect.="LPAD(COALESCE(" . $externalTableAlias . '.' . $externalObj->getDatabaseColumnName('sortOrder') . ",''),5,'0')";
            $querySelect.=",'#split#',";
          }
          $querySelect.=$externalTableAlias . '.' . $externalObj->getDatabaseColumnName('name');
          $querySelect.=",'#split#',";
          $querySelect.="COALESCE(" . $externalTableAlias . '.' . $externalObj->getDatabaseColumnName('color') . ",'')";
          $querySelect.=")"; // end of concat()
          $querySelect.=' using utf8mb4)'; // end of convert
          $querySelect.=' as ' . $fld;
        }
        $queryFrom.=' left join ' . $externalTable . ' as ' . $externalTableAlias . ' on ' . $table . "." . $obj->getDatabaseColumnName('id' . $externalClass) . ' = ' . $externalTableAlias . '.' . $externalObj->getDatabaseColumnName('id');
      } else if (($isIdFieldName or pq_strpos($fld, '__id')>0) and !$from) {
        $idTab+=1;
        // requested field is nameXXX => must fetch it from external table, using idXXX
        $posExt=pq_strpos($fld, "__id");
        if ($posExt>0) $externalClass=pq_substr(foreignKeyWithoutAlias($fld), 2);
        else $externalClass=pq_substr($fld, 4);
        if ($externalClass=='OriginLanguage') {
          $externalClass='Language';
        }
        $externalObj=new $externalClass();
        $externalTable=$externalObj->getDatabaseTableName();
        $externalTableAlias='T' . $idTab;
        if (property_exists($externalObj, '_calculateForColumn') and isset($externalObj->_calculateForColumn['name']) and $formatter[$numField]!='noCalculate' and $externalClass!='User') {
          $fieldCalc=$externalObj->_calculateForColumn["name"];
          $fieldCalc=pq_str_replace("(", "($externalTableAlias.", $fieldCalc);
          // $calculated=true;
          $querySelect.=$fieldCalc . ' as ' . ((Sql::isPgsql())?'"' . $fld . '"':$fld);
        } else if ($externalClass=='DocumentDirectory') {
          $querySelect.=$externalTableAlias . '.' . $externalObj->getDatabaseColumnName('location') . ' as ' . ((Sql::isPgsql())?'"' . $fld . '"':$fld);
        } else {
          if ($externalClass=='User') {
            $querySelect.="COALESCE($externalTableAlias.fullName, $externalTableAlias.name) as " . ((Sql::isPgsql())?'"' . $fld . '"':$fld);
          } else {
            $querySelect.=$externalTableAlias . '.' . $externalObj->getDatabaseColumnName('name') . ' as ' . ((Sql::isPgsql() and !$print)?'"' . $fld . '"':$fld);
          }
        }
        if (pq_substr($formatter[$numField], 0, 9)=='thumbName' or pq_substr($formatter[$numField], 0, 8)=='iconName') {
          $numField+=1;
          $formatter[$numField]='';
          $arrayWidth[$numField]='';
          $querySelect.=', ' . $table . "." . $obj->getDatabaseColumnName('id' . $externalClass) . ' as id' . $externalClass;
        }
        // if (! pq_stripos($queryFrom,$externalTable)) {
        $queryFrom.=' left join ' . $externalTable . ' as ' . $externalTableAlias . ' on ' . $table . "." . $obj->getDatabaseColumnName((pq_substr($fld, 0, 4)=="name")?'id' . pq_substr($fld, 4):$fld) . ' = ' . $externalTableAlias . '.' . $externalObj->getDatabaseColumnName('id');
        // }
      } else if (pq_strlen($fld)>5 and pq_substr($fld, 0, 5)=="color") {
        $idTab+=1;
        // requested field is colorXXX => must fetch it from external table, using idXXX
        $externalClass=pq_substr($fld, 5);
        $externalObj=new $externalClass();
        $externalTable=$externalObj->getDatabaseTableName();
        $externalTableAlias='T' . $idTab;
        $querySelect.=$externalTableAlias . '.' . $externalObj->getDatabaseColumnName('color') . ' as ' . ((Sql::isPgsql())?'"' . $fld . '"':$fld);
        // if (! pq_stripos($queryFrom,$externalTable)) {
        $queryFrom.=' left join ' . $externalTable . ' as ' . $externalTableAlias . ' on ' . $table . "." . $obj->getDatabaseColumnName('id' . $externalClass) . ' = ' . $externalTableAlias . '.' . $externalObj->getDatabaseColumnName('id');
        // }
      } else if ($from) {
        // Link to external table
        $externalClass=$from;
        $externalObj=new $externalClass();
        $externalTable=$externalObj->getDatabaseTableName();
        $externalTableAlias=pq_strtolower($externalClass);
        $refType=$objectClass;
        if ($objectClass=='TicketSimple'&&$externalClass=='VotingItem') $refType='Ticket';
        if (!pq_stripos($queryFrom, 'left join ' . $externalTable . ' as ' . $externalTableAlias)) {
          $queryFrom.=' left join ' . $externalTable . ' as ' . $externalTableAlias . ' on (' . $externalTableAlias . '.refId=' . $table . ".id" . ' and ' . $externalTableAlias . ".refType='" . $refType . "')";
        }
        if ($from=='OrganizationBudgetElementCurrent') {
          $queryFrom.=' and ' . $externalTableAlias . '.' . $externalObj->getDatabaseColumnName('year') . '=' . date('Y');
        }
        if ($isIdFieldName) {
          $idTab+=1;
          // requested field is nameXXX => must fetch it from external table, using idXXX
          $externalClassName=pq_substr($fld, 4);
          $externalObjName=new $externalClassName();
          $externalTableName=$externalObjName->getDatabaseTableName();
          $externalTableAliasName='T' . $idTab;
          $querySelect.=$externalTableAliasName . '.' . $externalObjName->getDatabaseColumnName('name') . ' as ' . ((Sql::isPgsql())?'"' . $fld . '"':$fld);
          $queryFrom.=' left join ' . $externalTableName . ' as ' . $externalTableAliasName . ' on ' . $externalTableAlias . "." . $externalObj->getDatabaseColumnName('id' . $externalClassName) . ' = ' . $externalTableAliasName . '.' . $externalObjName->getDatabaseColumnName('id');
        } else {
          $querySelect.=$externalTableAlias . '.' . $externalObj->getDatabaseColumnName($fld) . ' as ' . ((Sql::isPgsql())?'"' . $fld . '"':$fld);
        }
        if ($fld=='validatedEndDate') {
          $querySelect.=', ' . $externalTableAlias . '.' . $externalObj->getDatabaseColumnName('inheritedEndDate') . ' as ' . ((Sql::isPgsql())?'"inheritedEndDate"':'inheritedEndDate');
        }
        if (property_exists($externalObj, 'wbsSortable') and pq_strpos($queryOrderBy, $externalTableAlias . "." . $externalObj->getDatabaseColumnName('wbsSortable'))===false) {
          $queryOrderBy.=($queryOrderBy=='')?'':', ';
          $queryOrderBy.=" " . $externalTableAlias . "." . $externalObj->getDatabaseColumnName('wbsSortable') . " ";
        }
      } else if ($fld=='indicatorFileNoteLink') {
        $aff=new Affectable(getSessionUser()->id, true);
        $idTeamCurrentUser=$aff->idTeam;
        $userId=getSessionUser()->id;
        $note=new Note();
        $noteTable=$note->getDatabaseTableName();
        $link=new Link();
        $linkTable=$link->getDatabaseTableName();
        $attachment=new Attachment();
        $attachmentTable=$attachment->getDatabaseTableName();
        $querySelect.=' CONCAT(\'#Note#\',
	                                   (SELECT COUNT(n.id) FROM ' . $noteTable . ' n WHERE n.refType = \'' . $objectClass . '\' AND n.refId = ' . $table . '.id 
	                                       AND ( n.idPrivacy=1 OR (n.idPrivacy=2 and n.idTeam=' . Sql::fmtId($idTeamCurrentUser) . ') OR (n.idPrivacy=3 and n.idUser=' . Sql::fmtId($userId) . '))),
                                       \'#Link#\',
                                       (SELECT COUNT(l.id) FROM ' . $linkTable . ' l WHERE (l.ref1Type = \'' . $objectClass . '\' AND l.ref1Id = ' . $table . '.id 
                                           OR l.ref2Type = \'' . $objectClass . '\' AND l.ref2Id = ' . $table . '.id)),
                                       \'#Attach#\',
                                       (SELECT COUNT(a.id) FROM ' . $attachmentTable . ' a WHERE a.refType = \'' . $objectClass . '\' AND a.refId = ' . $table . '.id  
                                           AND ( a.idPrivacy=1 OR (a.idPrivacy=2 and a.idTeam=' . Sql::fmtId($idTeamCurrentUser) . ') OR (a.idPrivacy=3 and a.idUser=' . Sql::fmtId($userId) . '))))
                                AS ' . ((Sql::isPgsql())?'"indicatorFileNoteLink"':'indicatorFileNoteLink');
      } else if ($fld=='itemName') {
        $ass=new Assignment();
        $assTable=$ass->getDatabaseTableName();
        $queryRefTypes=sql::query("SELECT DISTINCT refType FROM $assTable");
        $refTypes=[];
        $isPgSql=Sql::isPgsql();
        foreach ($queryRefTypes as $row) {
          if ($isPgSql) {
            if (isset($row['reftype'])&&!in_array($row['reftype'], $refTypes)) {
              if (class_exists($row['reftype'])) $refTypes[]=$row['reftype'];
            }
          } else {
            if (isset($row['refType'])&&!in_array($row['refType'], $refTypes)) {
              if (class_exists($row['refType'])) $refTypes[]=$row['refType'];
            }
          }
        }
        $querySelect.=' CASE';
        foreach ($refTypes as $item) {
          $itemAlias=strtoupper(substr($item, 0, 2));
          $querySelect.=" WHEN $table.refType = '$item' THEN $itemAlias.name";
        }
        $querySelect.=' ELSE NULL END AS ' . ((Sql::isPgsql())?'"itemName"':'itemName');
        foreach ($refTypes as $item) {
          $itemObj=new $item();
          $itemTable=$itemObj->getDatabaseTableName();
          $itemAlias=strtoupper(substr($item, 0, 2));
          $itemLower=strtolower($item);
          $queryFrom.=" LEFT JOIN $itemTable AS $itemAlias ON $table.refType = '$item' AND $table.refId = $itemAlias.id ";
        }
      } else {
        // Simple field to add to request
        $querySelect.=$table . '.' . $obj->getDatabaseColumnName($fld) . ' as ' . ((Sql::isPgsql())?'"' . strtr($fld, '.', '_') . '"':strtr($fld, '.', '_'));
        if ($fld=='id' and property_exists($objectClass, $objectClass . 'PlanningElement')) {
          $externalClass=$objectClass . 'PlanningElement';
          $externalObj=new $externalClass();
          $externalTable=$externalObj->getDatabaseTableName();
          $externalTableAlias=pq_strtolower($externalClass);
          if (!pq_stripos($queryFrom, 'left join ' . $externalTable . ' as ' . $externalTableAlias)) {
            $queryFrom.=' left join ' . $externalTable . ' as ' . $externalTableAlias . ' on (' . $externalTableAlias . '.refId=' . $table . ".id" . ' and ' . $externalTableAlias . ".refType='" . $objectClass . "')";
          }
        }
      }
    }
  }
  if (property_exists($obj, 'idProject')) {
    $querySelect.=',' . $table . '.idProject as idproject';
  }
  if (get_class($obj)=='Affectation') {
    $idTab+=1;
    $externalClass='Affectable';
    $externalObj=new Affectable();
    $externalTable=$externalObj->getDatabaseTableName();
    $externalTableAlias='T' . $idTab;
    $fld='name';
    $querySelect.=($querySelect=='')?'':', ';
    $querySelect.="concat($externalTableAlias.name,'|',$externalTableAlias.fullName) as " . ((Sql::isPgsql())?'"' . $fld . '"':$fld);
    $queryFrom.=' left join ' . $externalTable . ' as ' . $externalTableAlias . ' on ' . $table . "." . $obj->getDatabaseColumnName('idResource') . ' = ' . $externalTableAlias . '.' . $externalObj->getDatabaseColumnName('id');
    $numField+=1;
    $formatter[$numField]='';
  }
  /*
   * if (get_class($obj)=='Assignment') {
   * $idTab+=1;
   * $externalClass = 'Assignment';
   * $externalObj=new Assignment();
   * $externalTable = $externalObj->getDatabaseTableName();
   * $externalTableAlias = 'T' . $idTab;
   *
   * $querySelect .= ($querySelect=='')?'':', ';
   * }
   */
}
// --- build order by clause
if ($objectClass=='DocumentDirectory') {
  $queryOrderBy.=($queryOrderBy=='')?'':', ';
  $queryOrderBy.=" " . $table . "." . $obj->getDatabaseColumnName('location');
} else if (property_exists($objectClass, 'wbsSortable')) {
  $queryOrderBy.=($queryOrderBy=='')?'':', ';
  $queryOrderBy.=" " . $table . "." . $obj->getDatabaseColumnName('wbsSortable');
} else if (property_exists($objectClass, 'bbsSortable')) {
  $queryOrderBy.=($queryOrderBy=='')?'':', ';
  $queryOrderBy.=" " . $table . "." . $obj->getDatabaseColumnName('bbsSortable');
} else if (property_exists($objectClass, 'sbsSortable')) {
  $queryOrderBy.=($queryOrderBy=='')?'':', ';
  $queryOrderBy.=" " . $table . "." . $obj->getDatabaseColumnName('sbsSortable');
} else if (property_exists($objectClass, 'sortOrder')) {
  $queryOrderBy.=($queryOrderBy=='')?'':', ';
  $queryOrderBy.=" " . $table . "." . $obj->getDatabaseColumnName('sortOrder');
} else {
  $queryOrderBy.=($queryOrderBy=='')?'':', ';
  $queryOrderBy.=" " . $table . "." . $obj->getDatabaseColumnName('id') . " desc";
}
jsonBuildWhereCriteria($querySelect, $queryFrom, $queryWhere, $queryOrderBy, $idTab, $arrayFilter, $obj);
$list=Plugin::getEventScripts('query', $objectClass);
foreach ($list as $script) {
  require $script; // execute code
}

// ==================== Constitute query and execute ============================================================
// --- Buimd where from "Select", "From", "Where" and "Order by" clauses built above
// gautier #1700
if ($objectClass=='Work') {
  $queryWhere=($queryWhere=='')?' 1=1':$queryWhere;
  $table=getListForSpecificRights('imputation');
  $getRessource=RequestHandler::getValue('exportRessourceAs');
  $date=RequestHandler::getValue('exportDateAs');
  $w=new Work();
  $wTable=$w->getDatabaseTableName();
  if (pq_substr($getRessource, 0, 1)=='C') {
    $getRessource=pq_substr($getRessource, 1);
    $queryWhere.=" and $wTable.idResource = $getRessource ";
  } else {
    $queryWhere.=" and $wTable.idResource in " . transformListIntoInClause($table);
  }
  if (pq_substr($date, 0, 1)=='W') {
    $dateWeekOrMonthOrYear='week';
  } elseif (pq_substr($date, 0, 1)=='M') {
    $dateWeekOrMonthOrYear='month';
  } elseif (pq_substr($date, 0, 1)=='Y') {
    $dateWeekOrMonthOrYear='year';
  } else {
    $date='All';
  }
  if ($date!='All') {
    $date=pq_substr($date, 1);
    $queryWhere.=" and $dateWeekOrMonthOrYear = " . Sql::str($date);
  }
}
// end gautier

if ($objectClass=='Budget') {
  $idSelectedBudget=RequestHandler::getValue('budgetParent');
  if (pq_trim($idSelectedBudget)) {
    $budg=new Budget($idSelectedBudget);
    $bbsSortable=$budg->bbsSortable;
    $queryWhere.=' and ' . $table . '.bbsSortable like "' . $bbsSortable . '%"';
  }
}

// MTY - LEAVE SYSTEM
// For Class of Leave System
if (isLeavesSystemActiv()) {
  if (pq_array_key_exists($obj->getMenuClass(), leavesSystemHabilitationList())) {
    $userId=getSessionUser()->id;
    // If access right is OWN = In leave system, owner is
    // ObjectClass = Employee
    // - Self or manager of employee (id)
    // ObjectClass = Other
    // - idUser or idEmployee
    // - Manager of the Employee
    if ($accessRightRead=="OWN") {
      // objectClass = Employee
      if ($objectClass=="Employee") {
        $empMng=new EmployeeManager(getSessionUser()->id);
        $managedEmployees=$empMng->getManagedEmployees();
        // Manager
        if ($managedEmployees) {
          $queryWhere.=($queryWhere==""?"":" AND ");
          $queryWhere.="$table.id in (" . getSessionUser()->id . ",";
          foreach ($managedEmployees as $key=>$name) {
            if ($key!=getSessionUser()->id) {
              $queryWhere.="$key,";
            }
          }
          $queryWhere.=") ";
          $queryWhere=pq_str_replace(",)", ")", $queryWhere);
        } // Self
        else {
          $queryWhere.=($queryWhere==""?"":" AND ");
          $queryWhere.="$table.id=" . getSessionUser()->id;
        }
      } // Other ObjectClass
      else {
        // - idUser or idEmployee
        $quote=false;
        if (property_exists($objectClass, "idUser")) {
          $queryWhere.=($queryWhere==""?"":" AND (") . "$table.idUser = $userId ";
          if (property_exists($objectClass, "idEmployee")) {
            $queryWhere.=($queryWhere==""?"":" OR ") . "$table.idEmployee = $userId ";
          }
          $quote=true;
        } elseif (property_exists($objectClass, "idEmployee")) {
          $queryWhere.=($queryWhere==""?"":" AND ") . "$table.idEmployee = $userId ";
        }
        // Manager
        if (property_exists($objectClass, "idEmployee")) {
          $empMng=new EmployeeManager(getSessionUser()->id);
          $managedEmployees=$empMng->getManagedEmployees();
          if ($managedEmployees) {
            if ($quote) {
              $queryWhere.=($queryWhere==""?"":" OR ");
            } else {
              $queryWhere.=($queryWhere==""?"":" AND ");
            }
            $queryWhere.="$table.idEmployee in (";
            foreach ($managedEmployees as $key=>$name) {
              $queryWhere.="$key,";
            }
            $queryWhere.=") ";
            $queryWhere=pq_str_replace(",)", ")", $queryWhere);
          }
        }
        if ($quote) {
          $queryWhere.=") ";
        }
      }
    }
  }
}
if ($outMode!='csv') {
  if (property_exists($obj, 'elementary')) { // PBER : For WorkCommand, do not list Parent lines (only elementary) to avoid wrong sums
                                             // $queryWhere.= ($queryWhere=='')?'':' and ';
                                             // $queryWhere.=" $table.elementary=1 ";
    if ($querySelect) $querySelect.=',';
    $querySelect.="$table.elementary as summable";
  } else if (property_exists($objectClass, $objectClass . 'PlanningElement') and pq_strpos($queryFrom, 'planningelement')!==false) {
    if ($querySelect) $querySelect.=',';
    $peTableInSelect=pq_strtolower($objectClass) . 'planningelement';
    if (!pq_strpos($queryFrom, $peTableInSelect)) $peTableInSelect='planningelement';
    $querySelect.=" $peTableInSelect.elementary as summable";
  }
}
// MTY - LEAVE SYSTEM
if (!$queryWhere) $queryWhere='1=1';
$query='select ' . $querySelect . $queryUOSelect . ' from ' . $queryFrom . ' where ' . $queryWhere . ' order by' . $queryOrderBy;
// --- Execute query
$result=Sql::query($query);
if (isset($debugJsonQuery) and $debugJsonQuery) { // Trace in configured to
  debugTraceLog("jsonQuery: " . $query); // Trace query
  debugTraceLog("  => error (if any) = " . Sql::$lastQueryErrorCode . ' - ' . Sql::$lastQueryErrorMessage);
  debugTraceLog("  => number of lines returned = " . Sql::$lastQueryNbRows);
}
$nbRows=0;
$dataType=array();
// --- Format for "printing"
if ($print) {
  if ($outMode=='csv') { // CSV mode
    $exportReferencesAs='name';
    global $hideScope;
    $hideScope='export';
    if (isset($_REQUEST['exportReferencesAs'])) {
      $exportReferencesAs=$_REQUEST['exportReferencesAs'];
    }
    $exportHtml=false;
    if (isset($_REQUEST['exportHtml']) and $_REQUEST['exportHtml']=='1') {
      $exportHtml=true;
    }
    $csvSep="";
    if (isset($_REQUEST['separatorCSV'])) {
      $csvSep=$_REQUEST['separatorCSV'];
    } else {
      $csvSep=Parameter::getGlobalParameter('csvSeparator');
    }
    $headers='caption';
    $csvQuotedText=true;
    if ($csvExportAll) {
      $exportReferencesAs='id';
      if (isset($csvSepExportAll)) $csvSep=$csvSepExportAll; // test should always be true
      $exportHtml=true;
      $headers='id';
      $csvQuotedText=false;
    }
    $obj=new $objectClass();
    if (method_exists($obj, 'setAttributes')) $obj->setAttributes();
    $first=true;
    $arrayFields=array();
    $arrayFields=$obj->getLowercaseFieldsArray(true);
    $arrayFieldsWithCase=$obj->getFieldsArray(true);
    if (isset($arrayDependantObjects[$objectClass])) {
      foreach ($arrayDependantObjects[$objectClass] as $incKey=>$incVal) {
        $incClass=get_class($incVal);
        $arrayFieldsInc=$incVal->getLowercaseFieldsArray(true);
        $arrayFieldsWithCaseInc=$incVal->getFieldsArray(true);
        foreach ($arrayFieldsInc as $incKey=>$incVal) {
          $arrayFields[pq_strtolower($incClass) . '_' . $incKey]=$incVal;
        }
        foreach ($arrayFieldsWithCaseInc as $incKey=>$incVal) {
          $arrayFieldsWithCase[pq_strtolower($incClass) . '_' . $incKey]=$incVal;
        }
      }
    }
    if ($objectClass!='Work') {
      $arrayFields['hyperlink']='hyperlink';
      $arrayFieldsWithCase['hyperlink']='Hyperlink';
    }
    if ($objectClass=='Assignment' and !isset($hiddenFields['itemName'])) {
      $arrayFields['itemname']='itemName';
      $arrayFieldsWithCase['itemName']=i18n('colItemName');
    }
    foreach ($arrayFieldsWithCase as $key=>$val) {
      if ($objectClass=='Assignment'&&$key=='itemName') {
        continue;
      }
      if (!SqlElement::isVisibleField($val)) {
        unset($arrayFields[pq_strtolower($key)]);
        continue;
      }
      $arrayFieldsWithCase[$key]=$obj->getColCaption($val);
      if (pq_substr($arrayFieldsWithCase[$key], 0, 1)=="[" and property_exists($obj, 'WorkElement')) {
        $weObj = $obj->WorkElement;
        $arrayFieldsWithCase[$key] = $weObj->getColCaption($val);
      }
      if (isset($arrayFieldsWithCase[$key]) and pq_substr($arrayFieldsWithCase[$key], 0, 1)=="[") {
        unset($arrayFields[pq_strtolower($key)]);
        continue;
      }
    }
    $hideHoursTicketDueDates=Parameter::getGlobalParameter('hideHoursTicketDueDates');
    while ($line=Sql::fetchLine($result)) {
      $refType=null;
      if ($first) {
        foreach ($line as $id=>$val) {
          if ($id=='refType') $refType=$val;
          if ((!isset($arrayFields[pq_strtolower($id)])) or ($objectClass=='GlobalView' and $id=='id')) {
            continue;
          }
          $colId=$id;
          if (Sql::isPgsql() and isset($arrayFields[$id])) {
            $colId=$arrayFields[$id];
          }
          if (property_exists($obj, $colId)) {
            $val=encodeCSV($obj->getColCaption($colId));
            if (Parameter::getGlobalParameter('workUnit')=='hours' and $obj->getDataType($colId)=='decimal' and pq_substr($colId, -4)=='Work') {
              $val.=' (' . GeneralWork::displayShortWorkUnit() . ')';
            }
          } else if (property_exists($obj, 'WorkElement') and property_exists('WorkElement', $colId)) {
            $we=new WorkElement();
            $val=encodeCSV($we->getColCaption($colId));
            if ($objectClass=='Ticket' and Parameter::getGlobalParameter('imputationUnit')=='hours' and $we->getDataType($colId)=='decimal' and pq_substr($colId, -4)=='Work') {
              $val.=' (' . GeneralWork::displayShortImputationUnit() . ')';
            }
          } else if (property_exists($obj, get_class($obj) . 'PlanningElement') and property_exists(get_class($obj) . 'PlanningElement', $colId)) {
            $peClass=get_class($obj) . 'PlanningElement';
            $pe=new $peClass();
            $val=encodeCSV($pe->getColCaption($colId));
            if (Parameter::getGlobalParameter('workUnit')=='hours' and $pe->getDataType($colId)=='decimal' and pq_substr($colId, -4)=='Work') {
              $val.=' (' . GeneralWork::displayShortWorkUnit() . ')';
            }
          } else {
            $val=encodeCSV($obj->getColCaption($colId)); // well, in the end, get default.
          }
          if ($headers=='id') $val=$colId;
          if (pq_strpos($colId, '_')!==null and isset($arrayDependantObjects[$objectClass])) {
            $split=pq_explode('_', $colId);
            foreach ($arrayDependantObjects[$objectClass] as $incKey=>$incVal) {
              $incKey=pq_ltrim($incKey, '_');
              if (pq_strtolower($incKey)==$split[0] and SqlElement::class_exists($incKey)) {
                $val=encodeCSV($incVal->getColCaption($split[1]) . ' (' . i18n($incKey) . ')');
                break;
              }
            }
          }
          if (pq_substr($id, 0, 9)=='idContext' and pq_strlen($id)==10) {
            $ctx=new ContextType(pq_substr($id, -1));
            $val=encodeCSV($ctx->name);
          }
          // $val=encodeCSV($id);
          $val=pq_str_replace($csvSep, ' ', $val);
          // if ($id!='id') { echo $csvSep ;}
          if ($objectClass=='Work' and Parameter::getGlobalParameter('imputationUnit')=='hours' and $id=='work') $val.=' (' . GeneralWork::displayShortImputationUnit() . ')';
          echo $val . $csvSep;
          $dataType[$id]=$obj->getDataType($id);
          $dataLength[$id]=$obj->getDataLength($id);
          if (!$dataLength[$id] and pq_substr($id, 0, 2)=='id' and pq_strlen($id)>2 and pq_substr($id, 2, 1)==pq_strtoupper(pq_substr($id, 2, 1))) {
            $dataType[$id]='int';
            $dataLength[$id]='12';
          }
          if ($id=='refId' and !property_exists($objectClass, 'refName') and $exportReferencesAs=='name' and $refType and !($objectClass=='Assignment' and !isset($hiddenFields['itemName']))) {
             echo encodeCSV(i18n('colName')) . $csvSep;
          }
        }
        if (pq_array_key_exists($id, $arrayUORefName)) {
          $titleUO='';
          foreach ($arrayUORefName as $nameUO) {
            $dataType[$nameUO]='decimal';
            $fullNameUO=pq_str_replace('_', ' - ', $nameUO);
            if (isset($arrayUOFullName[$nameUO])) $fullNameUO=$arrayUOFullName[$nameUO];
            $titleUO.=encodeCSV($fullNameUO) . $csvSep;
          }
          echo $titleUO;
        }
        echo "\r\n";
      }
      foreach ($line as $id=>$val) {
        $isItemName=($objectClass=='Assignment'&&$id=='itemName');
        if ((!$isItemName&&!isset($arrayFields[pq_strtolower($id)]) and (isset($arrayUORefName) and !pq_array_key_exists($id, $arrayUORefName)))||($objectClass=='GlobalView' and $id=='id')) continue;

        if ($id=='refType') $refType=$val;
        $foreign=false;
        $colId=$id;
        if (Sql::isPgsql() and isset($arrayFields[$id])) {
          $colId=$arrayFields[$id];
        }
        if (!isset($arrayFieldsWithCase[$colId]) and (isset($arrayUORefName) and !pq_array_key_exists($id, $arrayUORefName))) continue;
        // if (pq_substr($id, 0,2)=='id' and pq_strlen($id)>2) {
        if (isset($arrayFields[pq_strtolower($id)]) and isForeignKey($arrayFields[pq_strtolower($id)], $obj)) { // #3522 : Fix issue to export custom foreign items xxxx__idYyyyy
          $class=pq_substr(foreignKeyWithoutAlias($arrayFields[pq_strtolower($id)]), 2);
          // $class=pq_substr($arrayFields[pq_strtolower($id)], 2);
          if (pq_ucfirst($class)==$class) {
            $foreign=true;
            if ($class=="TargetVersion" or $class=="TargetProductVersion" or $class=="TargetComponentVersion" or $class=="OriginalVersion" or $class=="OriginalProductVersion" or $class=="OriginalComponentVersion") $class='Version';
            if ($class=="Resource" or $class=="ResourceSelect" or $class=="Contact") $class='Affectable';
            if ($exportReferencesAs=='name') {
              if ($id=='idDocumentDirectory') {
                $val=SqlList::getFieldFromId($class, $val, 'location');
              } else if (property_exists($class, 'name')) {
                $val=SqlList::getNameFromId($class, $val);
              }
            }
          }
        }
        if (isset($dataLength[$id]) and $dataLength[$id]>4000 and !$exportHtml) {
          if (isTextFieldHtmlFormatted($val)) {
            if (!$exportHtml) {
              $text=new Html2Text($val);
              $val=$text->getText();
            }
          } else {
            $val=br2nl($val);
          }
        }
        if (isset($dataType[$id]) and ($dataType[$id]=='datetime' or $dataType[$id]=='time')) {
          if (($id=='initialDueDateTime'||$id=='actualDueDateTime') and $hideHoursTicketDueDates=='YES' and $val) {
            $val=date('Y-m-d', pq_strtotime($val));
          }
          $val=convertServerTimeToUserTimezone($val);
        }
        $val=encodeCSV($val);
        if ($csvQuotedText) {
          $val=pq_str_replace('"', '""', $val);
        }
        // if ($id!='id') { echo $csvSep ;}
        if ((isset($dataType[$id]) and $dataType[$id]=='varchar' or $foreign) and $csvQuotedText) {
          echo '"' . $val . '"' . $csvSep;
        } else if ((isset($dataType[$id]) and $dataType[$id]=='decimal')) {
          // $withoutRounding=($objectClass == 'Work' and $id=='work')?true:false; //and Parameter::getGlobalParameter('imputationUnit')=='hours'
          // echo formatNumericOutput($val,$withoutRounding).$csvSep;
          if (($objectClass=='Work' and Parameter::getGlobalParameter('imputationUnit')=='hours' and $id=='work') or ($objectClass=='Ticket' and property_exists($obj, 'WorkElement') and property_exists('WorkElement', $colId) and Parameter::getGlobalParameter('imputationUnit')=='hours' and pq_substr($colId, -4)=='Work')) {
            $val=GeneralWork::displayImputation($val);
          } else if ($objectClass!='Ticket' and Parameter::getGlobalParameter('workUnit')=='hours' and pq_substr($colId, -4)=='Work') {
            $val=GeneralWork::displayWork($val);
          }
          echo formatNumericOutput($val) . $csvSep;
        } else if ($id=='hyperlink') {
          echo $obj->getReferenceUrl() . $val . $csvSep;
        } else {
          $val=pq_str_replace($csvSep, ' ', $val);
          echo $val . $csvSep;
        }
        if ($id=='refId' and !property_exists($objectClass, 'refName') and $exportReferencesAs=='name' and $refType and !($objectClass=='Assignment' and !isset($hiddenFields['itemName']))) {
          echo encodeCSV(SqlList::getNameFromId($refType, $val)) . $csvSep;
        }
      }
      $first=false;
      echo "\r\n";
    }
    if ($first) {
      echo encodeCSV(i18n("reportNoData"));
    }
  } else { // NON CSV mode : includes pure print and 'pdf' ($outMode=='pdf') mode
    echo '<br/>';
    echo '<div class="reportTableHeader" style="width:99%; font-size:150%;border: 0px solid #000000;">';
    echo (Sql::$lastQueryNbRows) . ' ' . i18n(((Sql::$lastQueryNbRows>1)?'menu':'') . $objectClass);
    echo '</div>';
    echo '<br/>';
    echo '<table align="" style="width:99%;' . ((isset($outModeBack) and $outModeBack=='pdf' and isWkHtmlEnabled())?'font-size:10pt':'') . '" ' . excelName() . '>';
    echo '<tr>';
    $layout=str_ireplace('width="', 'style="' . ((isNewGui() and $outMode!='pdf')?'border:1px solid white;':'border:1px solid black;') . 'width:', $layout);
    $layout=str_ireplace('<th ', '<th ' . excelFormatCell('header', 40) . ' class="reportTableHeader" ', $layout);
    if ($objectClass=='GlobalView') $layout=pq_str_replace('<th ' . excelFormatCell('header', 40) . ' class="reportTableHeader" field="id" style="border:1px solid black;width:0%">id</th>', '', $layout);
    echo $layout;
    echo '</tr>';
    if (Sql::$lastQueryNbRows>0) {
      $hiddenField='<span style="color:#AAAAAA">(...)</span>';
      $hideHoursTicketDueDates=Parameter::getGlobalParameter('hideHoursTicketDueDates');
      while ($line=Sql::fetchLine($result)) {
        echo '<tr>';
        $numField=0;
        $idProject=($objectClass=='Project')?$line['id']:((isset($line['idproject']))?$line['idproject']:null);
        foreach ($line as $id=>$val) {
          if ($id=='inheritedEndDate') continue;
          $numField+=1;
          $disp="";
          $bgColor=null;
          if ($objectClass=='GlobalView' and $id=='id') continue;
          if (!isset($arrayWidth[$numField]) or $arrayWidth[$numField]=='') continue;
          if ($formatter[$numField]=="colorNameFormatter") {
            $disp=colorNameFormatter($val);
            $tab=pq_explode("#split#", $val);
            if (count($tab)>1) {
              if (count($tab)==2) {
                $bgColor=$tab[1];
              } else if (count($tab)==3) {
                $bgColor=$tab[2];
              }
            }
          } else if ($formatter[$numField]=="classNameFormatter") {
            $disp=classNameFormatter($val);
          } else if ($formatter[$numField]=="colorTranslateNameFormatter") {
            $disp=colorTranslateNameFormatter($val);
          } else if ($formatter[$numField]=="booleanFormatter") {
            $disp=booleanFormatter($val);
          } else if ($formatter[$numField]=="colorFormatter") {
            $disp=colorFormatter($val);
          } else if ($formatter[$numField]=="dateTimeFormatter") {
            if (($id=='initialDueDateTime'||$id=='actualDueDateTime') and $hideHoursTicketDueDates=='YES') {
              $disp=dateFormatter($val);
            } else {
              $disp=dateTimeFormatter($val);
            }
          } else if ($formatter[$numField]=="dateFormatter") {
            if ($id=='validatedEndDate' and !$val and isset($line['inheritedEndDate']) and $line['inheritedEndDate']) {
              $disp='<span style="font-style:italic;color:#cccccc">' . dateFormatter($line['inheritedEndDate']) . '</span>';
            } else {
              $disp=dateFormatter($val);
            }
          } else if ($formatter[$numField]=="timeFormatter") {
            $disp=timeFormatter($val);
          } else if ($formatter[$numField]=="translateFormatter") {
            $disp=translateFormatter($val);
          } else if ($formatter[$numField]=="tagFormatter") {
            $disp=tagFormatter($val);
          } else if ($formatter[$numField]=="percentFormatter") {
            $disp=percentFormatter($val, ($outMode=='pdf')?false:true);
          } else if ($formatter[$numField]=="numericFormatter") {
            $disp=numericFormatter($val);
          } else if ($formatter[$numField]=="sortableFormatter") {
            $disp=sortableFormatter($val);
          } else if ($formatter[$numField]=="workFormatter") {
            if ($idProject and !$user->getWorkVisibility($idProject, $id)) {
              $disp=$hiddenField;
            } else {
              $class=get_class($obj);
              if ($class=='Ticket' or $class=='TicketSimple' or $class='Resource') {
                $disp=imputationFormatter($val);
              } else {
                $disp=workFormatter($val);
              }
            }
          } else if ($formatter[$numField]=="costFormatter") {
            if ($idProject and !$user->getCostVisibility($idProject, $id)) {
              $disp=$hiddenField;
            } else {
              $disp=costFormatter($val);
            }
          } else if ($formatter[$numField]=="costFormatterLocal") {
            if ($idProject and !$user->getCostVisibility($idProject, $id)) {
              $disp="";
            } else {
              $disp=costFormatterLocal($val, $idProject);
            }
          } else if ($formatter[$numField]=="iconFormatter") {
            $disp=iconFormatter($val);
          } else if ($formatter[$numField]=="iconNameFormatter") {
            $disp=iconFormatter($val);
          } else if (pq_substr($formatter[$numField], 0, 9)=='thumbName') {
            // $disp=thumbFormatter($objectClass,$line['id'],pq_substr($formatter[$numField],5));
            $nameClass=pq_substr($id, 4);
            if (Sql::isPgsql()) $nameClass=pq_strtolower($nameClass);
            if ($val and $showThumb) {
              $size=pq_substr($formatter[$numField], 9);
              $radius=round($size/2, 0);
              $thumbUrl=Affectable::getThumbUrl('Affectable', $line['id' . $nameClass], pq_substr($formatter[$numField], 9), false, ($outMode=='pdf')?true:false);
              if (pq_substr($thumbUrl, 0, 6)=='letter') {
                $disp.=formatLetterThumb($line['id' . $nameClass], $size, null, null, null) . '&nbsp;' . $val;
              } else {
                if ($outMode=='pdf') {
                  $disp='<span style="position:relative;border-radius:50%;height:' . ($size-2) . 'px;width:' . ($size-2) . 'px; top:1px;" >';
                  $disp.='<img style="border-radius:' . $radius . 'px;height:' . $size . 'px;float:left" src="' . $thumbUrl . '" />';
                  $disp.='&nbsp;&nbsp;' . $val;
                  $disp.='</span>';
                } else {
                  $disp='<div style="text-align:left;">';
                  $disp.='<img style="border-radius:' . $radius . 'px;height:' . $size . 'px;float:left" src="' . $thumbUrl . '"';
                  $disp.='/>';
                  $disp.='<div style="margin-left:' . ($size+2) . 'px;">' . $val . '</div>';
                  $disp.='</div>';
                }
              }
            } else {
              $disp=htmlEncode($val);
            }
          } else if (pq_substr($formatter[$numField], 0, 5)=='thumb') {
            $thumClass=($objectClass=='ResourceTeam')?'Resource':$objectClass;
            $disp=thumbFormatter($thumClass, $line['id'], pq_substr($formatter[$numField], 5));
          } else if ($formatter[$numField]=="privateFormatter") {
            $disp=privateFormatter($val);
          } else {
            $disp=htmlEncode($val);
          }
          $colWidth=$arrayWidth[$numField];
          $colWidthExcel=intval($colWidth)*2;
          echo '<td class="tdListPrint ' . ((pq_substr($formatter[$numField], 0, 5)=='color')?'colorNameData':'') . '" style="white-space:normal;width:' . $colWidth . ';" ' . excelFormatCell('data', $colWidthExcel, null, $bgColor) . '>' . $disp . '</td>';
        }
        echo '</tr>';
      }
    }
    echo "</table>";
    // echo "</div>";
  }
} else {
  // return result in json format
  echo '{"identifier":"id",';
  echo ' "items":[';
  if (Sql::$lastQueryNbRows>0) {
    $hideHoursTicketDueDates=Parameter::getGlobalParameter('hideHoursTicketDueDates');
    while ($line=Sql::fetchLine($result)) {
      if ($objectClass=='Term') { // Attention, this part main reduce drastically performance
        $term=new Term($line['id']);
        $line['validatedAmount']=$term->validatedAmount;
        $line['validatedDate']=$term->validatedDate;
        $line['plannedAmount']=$term->plannedAmount;
        $line['plannedDate']=$term->plannedDate;
      }
      echo (++$nbRows>1)?',':'';
      echo '{';
      $nbFields=0;
      $idProject=($objectClass=='Project')?((isset($line['id']))?$line['id']:null):((isset($line['idproject']))?$line['idproject']:null);
      foreach ($line as $id=>$val) {
        if ($id=='idproject' or $id=='inheritedEndDate') continue;
        echo (++$nbFields>1)?',':'';
        $numericLength=0;
        if (!isset($formatter[$nbFields])) $formatter[$nbFields]='';
        if ($id=='id') {
          $numericLength=6;
        } else if ($formatter[$nbFields]=='classNameFormatter') {
          $val=i18n($val) . '|' . $val;
        } else if ($formatter[$nbFields]=='percentFormatter') {
          $numericLength=3;
          if ($val<0) $numericLenght=0;
        } else if ($formatter[$nbFields]=='workFormatter') {
          $numericLength=9;
          if ($val<0) $numericLength=0;
          if ($idProject and !$user->getWorkVisibility($idProject, $id)) {
            $val='-';
            $numericLength=0;
          }
        } else if ($formatter[$nbFields]=='costFormatter') {
          $numericLength=9;
          if ($val<0) $numericLength=0;
          if ($idProject and !$user->getCostVisibility($idProject, $id)) {
            $val='-';
            $numericLength=0;
          }
        } else if ($formatter[$nbFields]=='costFormatterLocal') {
          $numericLength=9;
          if ($val<0) $numericLength=0;
          if ($idProject and !$user->getCostVisibility($idProject, $id)) {
            $val='-';
            $numericLength=0;
          } else if ($idProject and !Project::hasProjectCurrency($idProject)) {
            $val='-';
            $numericLength=0;
          } else if ($idProject) {
            $currency=Project::getProjectCurrency($idProject);
            $currencyPosition=Project::getProjectCurrencyPosition($idProject);
            $val="$val#$currency#$currencyPosition";
          }
        } else if ($formatter[$nbFields]=='numericFormatter') {
          $numericLength=9;
          if ($val<0) $numericLength=0;
          if ((pq_strtolower($id)=='warningvalue' or pq_strtolower($id)=='alertvalue') and !$val) {
            $numericLength=null;
            $val='NaN';
          }
        } else if ($formatter[$nbFields]=='dateTimeFormatter') {
          if (($id=='initialDueDateTime'||$id=='actualDueDateTime') and $hideHoursTicketDueDates=='YES' and $val) {
            $val=date('Y-m-d', pq_strtotime($val));
            $val=htmlFormatDate($val);
          }
          $val=convertServerTimeToUserTimezone($val);
        } else if ($formatter[$nbFields]=='timeFormatter' or pq_substr($id, -4)=='Time') {
          $val=convertServerTimeToUserTimezone($val);
        }
        if ($id=='validatedEndDate' and !$val and isset($line['inheritedEndDate']) and $line['inheritedEndDate']) {
          $val=$line['inheritedEndDate'] . '#';
        }
        if ($id=='colorNameRunStatus') {
          $split=pq_explode('#', $val);
          foreach ($split as $ix=>$sp) {
            if ($ix==0) {
              $val=$sp;
            } else if ($ix==2) {
              $val.='#' . i18n($sp);
            } else {
              $val.='#' . $sp;
            }
          }
        }
        if (pq_substr($formatter[$nbFields], 0, 8)=='iconName') {
          $nameClass=pq_substr($id, 4);
          if (Sql::isPgsql()) $nameClass=pq_strtolower($nameClass);
          if ($val and property_exists($nameClass, 'icon')) {
            $val=$val . '#!#' . SqlList::getFieldFromId($nameClass, $line['id' . $nameClass], 'icon');
          }
        }
        if (pq_substr($formatter[$nbFields], 0, 5)=='thumb') {
          if (pq_substr($formatter[$nbFields], 0, 9)=='thumbName') {
            $nameClass=pq_substr($id, 4);
            if (Sql::isPgsql()) $nameClass=pq_strtolower($nameClass);
            if ($val and $showThumb) {
              $val=$val . '#!#' . Affectable::getThumbUrl('Affectable', $line['id' . $nameClass], pq_substr($formatter[$nbFields], 9)) . '#' . $val;
            } else {
              $val=$val . '#!#' . "####$val";
            }
          } else if (Affectable::isAffectable($objectClass)) {
            $val=Affectable::getThumbUrl($objectClass, $line['id'], $val) . '##' . pq_strtoupper(pq_mb_substr(SqlList::getNameFromId('Affectable', $line['id']), 0, 1, 'UTF-8'));
          } else {
            $image=SqlElement::getSingleSqlElementFromCriteria('Attachment', array('refType'=>$objectClass, 'refId'=>$line['id']));
            if ($image->id and $image->isThumbable()) {
              $val=getImageThumb($image->getFullPathFileName(), $val) . '#' . htmlEncodeJson($image->id, 6) . '#' . htmlEncodeJson($image->fileName);
            } else {
              $val="##";
            }
          }
        }
        if ($id=='name') {
          $iconClass='';
          if (get_class($obj)=='ResourceAll' or get_class($obj)=='ResourceAllNoMaterial') {
            $idResource=SqlList::getIdFromName('ResourceAll', $val);
            $isResourceTeam=SqlList::getFieldFromId('ResourceAll', $idResource, 'isResourceTeam');
            $iconClass=($isResourceTeam)?'iconResourceTeam#:#:#:#:#:#':''; // Seperator for iconClass used in projeqtorFormatter.js function formatUpperName()
          }
          $val=htmlEncodeJson($val);
          if (property_exists($obj, '_isNameTranslatable') and $obj->_isNameTranslatable) {
            $val.='#!#!#!#!#!#' . pq_mb_strtoupper(suppr_accents(i18n($val)));
          } else {
            $nameOupper=pq_mb_strtoupper(suppr_accents($val));
            $val=$iconClass . $nameOupper . '#!#!#!#!#!#' . $val;
          }
          echo '"' . htmlEncode($id) . '":"' . $val . '"';
        } else {
          echo '"' . htmlEncode($id) . '":"' . htmlEncodeJson($val, $numericLength) . '"';
        }
      }
      echo '}';
    }
  }
  echo ']';
  // echo ', "numberOfRow":"' . $nbRows . '"' ;
  echo ' }';
}
// end:
// echo '<div class="messageError" >'.i18n('ErrorNotSameWorkUnit').'</div>';
?>
