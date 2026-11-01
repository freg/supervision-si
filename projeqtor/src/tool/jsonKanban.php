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
 * Get the list of objects, in Json format, to display the kanban
 */
require_once "../tool/projeqtor.php";
session_write_close();
scriptLog('   ->/tool/jsonKanban.php');

// ============================================================================
// PARAMÈTRES DE REQUÊTE
// ============================================================================
$onlyRefresh = RequestHandler::getBoolean('onlyRefresh');
$oldColumn = RequestHandler::getValue('oldColumn');
$newColumn = RequestHandler::getValue('newColumn');
$onlyRefresh = ($oldColumn and $newColumn)?true:$onlyRefresh;
$arrayRefreshColumn=array($oldColumn=>$oldColumn, $newColumn=>$newColumn);

// ============================================================================
// PARAMÈTRES KANBAN
// ============================================================================
$idKanban = Parameter::getUserParameter("kanbanIdKanban");
$kanB = new Kanban($idKanban, true);
$json = $kanB->param;
$jsonDecode = ($json !== null and $json !== '') ? json_decode($json, true) : array();
if(!is_array($jsonDecode)) $jsonDecode = array();
$typeKanbanC = (isset($jsonDecode['typeData']) and $jsonDecode['typeData'] != '') ? $jsonDecode['typeData'] : 'Ticket';
$type = $kanB->type;
$isColorBlind = (Parameter::getUserParameter('colorBlindPlanning') == 'YES') ? true : false;

// ============================================================================
// PARAMÈTRES AFFICHAGE
// ============================================================================
$seeWork=Parameter::getUserParameter("kanbanSeeWork");
$showIdle = Parameter::getUserParameter("kanbanShowIdle");
$kanbanFullWidthElement = Parameter::getUserParameter("kanbanFullWidthElement");
$hideBacklog = Parameter::getUserParameter("kanbanHideBacklog");
$hideParentActivities = Parameter::getUserParameter("kanbanHideParentActivities");
$hideStatus = Parameter::getUserParameter("kanbanHideStatus");
$hideProduct = Parameter::getUserParameter("kanbanHideProduct");
$hideActivityPlanning = Parameter::getUserParameter("kanbanHideActivityPlanning");
$hideResponsible = Parameter::getUserParameter("kanbanHideResponsible");
$hidePriority = Parameter::getUserParameter("kanbanHidePriority");
$hideUrgency = Parameter::getUserParameter("kanbanHideCriticality");
$hidePlannedDate = Parameter::getUserParameter("kanbanHidePlannedDate");
$hideType = Parameter::getUserParameter("kanbanHideType");
$hideProjectName = Parameter::getUserParameter("kanbanHideProjectName");
$hideColorTitle = Parameter::getUserParameter("kanbanHideColorTitle");
$modeColorTitle = Parameter::getUserParameter( "kanbanModeColorTitle" . Parameter::getUserParameter("kanbanIdKanban") );
$modeColorTitle = (!$modeColorTitle)? 'noColor' : $modeColorTitle;
$orderBy = Parameter::getUserParameter('kanbanOrderBy');
$colorOnTitleOrFullTile = Parameter::getUserParameter("kanbanColorOnTitleOrFullTile");

// ============================================================================
// DÉTERMINATION DES PROPRIÉTÉS DU TYPE
// ============================================================================
$obj  = new $typeKanbanC();
$hasVersion = property_exists($typeKanbanC, 'idTargetProductVersion');
$hasMilestone = property_exists($typeKanbanC, "idMilestone");
$hasUrgency = property_exists($typeKanbanC, "idUrgency");
$hasPriority = property_exists($typeKanbanC, "idPriority");
$hasActivity = property_exists($typeKanbanC, "idActivity");

$pwe = new PlanningElement();
$hasWorkElement = false;
if($typeKanbanC == 'Activity'){
  $pwe = new PlanningElement();
  $hasWorkElement = true;
}else if($typeKanbanC != 'Requirement' and $typeKanbanC != 'Action'){
  $pwe = new WorkElement();
  $hasWorkElement = true;
}

$hasVote = false;
if (Module::isModuleActive('moduleVoting')) {
  if(property_exists($typeKanbanC, "VotingItem")){
    $hasVote = true;
  }
}

// ============================================================================
// GESTION DES COLONNES PAR TYPE
// ============================================================================

$columnList = array();
$jsonColumnList = array();
$backlogColumnList = array();  // Liste des colonnes de type "backlog" pour chaque type de colonne
$columnRanges = array();  // Pour stocker les plages de statuts de chaque colonne (type Status)
$idBacklogColumn = 0;

// Pour Status : le backlog correspond aux statuts avec forAgileScrum = '0'
$where = "forAgileScrum = '0' and (idle = '0' or isCopyStatus = '1')";
$statusList = SqlList::getListWithCrit('Status',$where,'id',null,true);
if($type == 'Status'){
  $idBacklogColumn = array_key_first($statusList);
  $backlogColumnList = $statusList;
}

foreach ($arrayRefreshColumn as $key=>$column){
  if($column == 'backlog')$arrayRefreshColumn[$key]=$idBacklogColumn;
}

// Construction de la liste des colonnes et identification du backlog
if(isset($jsonDecode['column']) and is_array($jsonDecode['column'])){
  foreach($jsonDecode['column'] as $idx => $col){
    $idCol = ($col['from'] == 'n')?'0':$col['from'];
    // Ne traiter que les colonnes à rafraîchir si onlyRefresh est actif
    if(!$onlyRefresh or in_array($idCol, $arrayRefreshColumn)){
      
      // Détection colonne cachée
      $hideColumnParam = "kanbanHideColumn_".$idKanban."_".$idCol;
      $hidedColumn=Parameter::getUserParameter($hideColumnParam);

      // Initialisation de la colonne dans le JSON
      if($idCol != $idBacklogColumn){
        $columnList[$idCol] = $idCol;
        $jsonColumnList[$idCol] = array();
        $jsonColumnList[$idCol]['id'] = $idCol;
        $jsonColumnList[$idCol]['type'] = $type;
        $jsonColumnList[$idCol]['itemlist'] = array();
        $jsonColumnList[$idCol]['hidden'] = $hidedColumn?'1':'no';
        $jsonColumnList[$idCol]['fullwidthelement'] = $kanbanFullWidthElement;
        $jsonColumnList[$idCol]['hideidle'] = $showIdle;
        $jsonColumnList[$idCol]['hideworks'] = $seeWork;
        $jsonColumnList[$idCol]['hidestatus'] = $hideStatus;
        $jsonColumnList[$idCol]['hidetype'] = $hideType;
        $jsonColumnList[$idCol]['hideprojectname'] = $hideProjectName;
        $jsonColumnList[$idCol]['hideproduct'] = $hideProduct;
        $jsonColumnList[$idCol]['hideactivityplanning'] = $hideActivityPlanning;
        $jsonColumnList[$idCol]['hideresponsible'] = $hideResponsible;
        $jsonColumnList[$idCol]['hidepriority'] = $hidePriority;
        $jsonColumnList[$idCol]['hideurgency'] = $hideUrgency;
        $jsonColumnList[$idCol]['hideplanneddate'] = $hidePlannedDate;
        $jsonColumnList[$idCol]['hidecolortitle'] = $hideColorTitle;
        $jsonColumnList[$idCol]['modecolortitle'] = $modeColorTitle;
        $jsonColumnList[$idCol]['colorontitleorfulltile'] = $colorOnTitleOrFullTile;
        $jsonColumnList[$idCol]['workunit'] = Work::displayShortWorkUnit();
      }

      // Pour le type Status, calculer la plage de statuts de cette colonne
      // Le calcul doit utiliser TOUTES les colonnes (cachées comprises) pour
      // que la plage d'une colonne visible ne déborde pas sur les statuts
      // d'une colonne cachée voisine.
      if($type == 'Status' && $idCol != '0'){
        $nextFrom = null;
        for($j = $idx + 1; $j < count($jsonDecode['column']); $j++){
          $nextCol = $jsonDecode['column'][$j];
          $nextIdCol = ($nextCol['from'] == 'n')?'0':$nextCol['from'];
          if($nextIdCol != '0'){
            $nextFrom = $nextIdCol;
            break;
          }
        }
        $columnRanges[$idCol] = array('from' => $idCol, 'to' => $nextFrom, 'hidden' => $hidedColumn?true:false);
      }
    }
  }
}

// ============================================================================
// GESTION SPÉCIFIQUE DU BACKLOG SELON LE TYPE DE COLONNE
// ============================================================================
$refreshBacklog = false;
$onlyRefreshBacklog = false;

if($type == 'Status'){
  // Ajustement des colonnes old/new pour le backlog
  $oldColumn = ($idBacklogColumn == $oldColumn)?'backlog':$oldColumn;
  $newColumn = ($idBacklogColumn == $newColumn)?'backlog':$newColumn;
  
  // Détermination du rafraîchissement du backlog
  $refreshBacklog = (($hideBacklog == '' or $hideBacklog == 'on' or $hideBacklog == '1')
      and (!$onlyRefresh or $idBacklogColumn == $oldColumn or $idBacklogColumn == $newColumn)) ? true : false;
      $onlyRefreshBacklog = ($oldColumn == 'backlog' and $newColumn == 'backlog') ? true : false;
      
      // Ajout de la colonne backlog si nécessaire
      if($refreshBacklog or $onlyRefreshBacklog){
        if(!isset($jsonColumnList[$idBacklogColumn])){
          $jsonColumnList[$idBacklogColumn] = array();
          $jsonColumnList[$idBacklogColumn]['id'] = $idBacklogColumn;
          $jsonColumnList[$idBacklogColumn]['type'] = $type;
          $jsonColumnList[$idBacklogColumn]['itemlist'] = array();
          $jsonColumnList[$idBacklogColumn]['fullwidthelement'] = $kanbanFullWidthElement;
          $jsonColumnList[$idBacklogColumn]['hideidle'] = $showIdle;
          $jsonColumnList[$idBacklogColumn]['hideworks'] = $seeWork;
          $jsonColumnList[$idBacklogColumn]['hidestatus'] = $hideStatus;
          $jsonColumnList[$idBacklogColumn]['hidetype'] = $hideType;
          $jsonColumnList[$idBacklogColumn]['hideprojectname'] = $hideProjectName;
          $jsonColumnList[$idBacklogColumn]['hideproduct'] = $hideProduct;
          $jsonColumnList[$idBacklogColumn]['hideactivityplanning'] = $hideActivityPlanning;
          $jsonColumnList[$idBacklogColumn]['hideresponsible'] = $hideResponsible;
          $jsonColumnList[$idBacklogColumn]['hidepriority'] = $hidePriority;
          $jsonColumnList[$idBacklogColumn]['hideurgency'] = $hideUrgency;
          $jsonColumnList[$idBacklogColumn]['hideplanneddate'] = $hidePlannedDate;
          $jsonColumnList[$idBacklogColumn]['hidecolortitle'] = $hideColorTitle;
          $jsonColumnList[$idBacklogColumn]['modecolortitle'] = $modeColorTitle;
          $jsonColumnList[$idBacklogColumn]['colorontitleorfulltile'] = $colorOnTitleOrFullTile;
          $jsonColumnList[$idBacklogColumn]['workunit'] = Work::displayShortWorkUnit();
        }
      }
      
      // Mise à jour de arrayRefreshColumn si nécessaire
      if($onlyRefreshBacklog){
        $arrayRefreshColumn = $statusList;
      }
      
}else{
  // Pour les autres types (TargetProductVersion, Activity, Milestone)
  // Le backlog correspond à la valeur NULL ou 0
  $idBacklogColumn = 0;
  $backlogColumnList = array(0 => 0);
  
  // Ajustement de oldColumn et newColumn
  $oldColumn = ($oldColumn == '0' or $oldColumn == 'backlog')?'backlog':$oldColumn;
  $newColumn = ($newColumn == '0' or $newColumn == 'backlog')?'backlog':$newColumn;
  
  // Détermination du rafraîchissement du backlog
  $refreshBacklog = (($hideBacklog == '' or $hideBacklog == 'on' or $hideBacklog == '1')
      and (!$onlyRefresh or $idBacklogColumn == $oldColumn or $idBacklogColumn == $newColumn
          or $oldColumn == 'backlog' or $newColumn == 'backlog')) ? true : false;
          $onlyRefreshBacklog = ($oldColumn == 'backlog' and $newColumn == 'backlog') ? true : false;
          
          // Ajout de la colonne backlog si nécessaire
          if($refreshBacklog or $onlyRefreshBacklog){
            if(!isset($jsonColumnList[$idBacklogColumn])){
              $jsonColumnList[$idBacklogColumn] = array();
              $jsonColumnList[$idBacklogColumn]['id'] = $idBacklogColumn;
              $jsonColumnList[$idBacklogColumn]['type'] = $type;
              $jsonColumnList[$idBacklogColumn]['itemlist'] = array();
              $jsonColumnList[$idBacklogColumn]['fullwidthelement'] = $kanbanFullWidthElement;
              $jsonColumnList[$idBacklogColumn]['hideidle'] = $showIdle;
              $jsonColumnList[$idBacklogColumn]['hideworks'] = $seeWork;
              $jsonColumnList[$idBacklogColumn]['hidestatus'] = $hideStatus;
              $jsonColumnList[$idBacklogColumn]['hidetype'] = $hideType;
              $jsonColumnList[$idBacklogColumn]['hideprojectname'] = $hideProjectName;
              $jsonColumnList[$idBacklogColumn]['hideproduct'] = $hideProduct;
              $jsonColumnList[$idBacklogColumn]['hideactivityplanning'] = $hideActivityPlanning;
              $jsonColumnList[$idBacklogColumn]['hideresponsible'] = $hideResponsible;
              $jsonColumnList[$idBacklogColumn]['hidepriority'] = $hidePriority;
              $jsonColumnList[$idBacklogColumn]['hideurgency'] = $hideUrgency;
              $jsonColumnList[$idBacklogColumn]['hideplanneddate'] = $hidePlannedDate;
              $jsonColumnList[$idBacklogColumn]['hidecolortitle'] = $hideColorTitle;
              $jsonColumnList[$idBacklogColumn]['modecolortitle'] = $modeColorTitle;
              $jsonColumnList[$idBacklogColumn]['colorontitleorfulltile'] = $colorOnTitleOrFullTile;
              $jsonColumnList[$idBacklogColumn]['workunit'] = Work::displayShortWorkUnit();
            }
          }
}

// ============================================================================
// CONSTRUCTION DES OBJETS NÉCESSAIRES
// ============================================================================
$act  = new Activity();
$st   = new Status();
$p    = new Project();
$aff  = new Affectable();
$n    = new Note();
$tpv  = new Version();
$prio = new Priority();
$urg  = new Urgency();
$vti = new VotingItem();
$votingObj = new Voting();
$votingAttrObj = new VotingAttribution();
$votingUseRuleObj = new VotingUseRule();

$typeClass = ucfirst($typeKanbanC).'Type';
$ty = new $typeClass();

// ============================================================================
// CONSTRUCTION DE LA REQUÊTE SQL
// ============================================================================

// ====== SELECT ======
$querySelect  = " obj.id                      AS id, ";
$querySelect .= " obj.name                    AS name, ";
$querySelect .= " obj.id".$typeKanbanC."Type  AS idtype, ";
$querySelect .= " obj.idStatus                AS idstatus, ";
$querySelect .= " obj.idProject               AS idproject, ";

// Champ de la colonne (dépend du type de Kanban)
$columnField = 'id'.$type;
$querySelect .= " obj.".$obj->getDatabaseColumnName($columnField)." AS columnvalue, ";

if($hasUrgency){
  $querySelect .= " obj.idUrgency             AS idurgency, ";
  $querySelect .= " urg.name                  AS urgencyname, ";
  $querySelect .= " urg.color                 AS urgencycolor, ";
}else{
  $querySelect .= " NULL                      AS idurgency, ";
  $querySelect .= " NULL                      AS urgencyname, ";
  $querySelect .= " NULL                      AS urgencycolor, ";
}

if($hasPriority){
  $querySelect .= " obj.idPriority            AS idpriority, ";
  $querySelect .= " prio.name                 AS priorityname, ";
  $querySelect .= " prio.color                AS prioritycolor, ";
}else{
  $querySelect .= " NULL                      AS idpriority, ";
  $querySelect .= " NULL                      AS priorityname, ";
  $querySelect .= " NULL                      AS prioritycolor, ";
}

if($hasVersion){
  $querySelect .= " obj.".$obj->getDatabaseColumnName('idTargetProductVersion')." AS idtargetproductversion, ";
  $querySelect .= " tpv.name                  AS targetproductversionname, ";
}else{
  $querySelect .= " NULL                      AS idtargetproductversion, ";
  $querySelect .= " NULL                      AS targetproductversionname, ";
}

if($hasMilestone){
  $querySelect .= " obj.idMilestone           AS idmilestone, ";
}else{
  $querySelect .= " NULL                      AS idmilestone, ";
}

if($hasActivity){
  $querySelect .= " obj.idActivity            AS idactivity, ";
  $querySelect .= " act.name                  AS activityname, ";
}else{
  $querySelect .= " NULL                      AS idactivity, ";
  $querySelect .= " NULL                      AS activityname, ";
}

if($hasWorkElement){
  $querySelect .= " pwe.plannedWork           AS plannedwork, ";
  $querySelect .= " pwe.realWork              AS realwork, ";
  $querySelect .= " pwe.leftWork              AS leftwork, ";
}else{
  $querySelect .= " NULL                      AS plannedwork, ";
  $querySelect .= " NULL                      AS realwork, ";
  $querySelect .= " NULL                      AS leftwork, ";
}

if($typeKanbanC == 'Activity' and $hasWorkElement){
  $querySelect .= " pwe.validatedEndDate      AS validatedenddate, ";
  $querySelect .= " pwe.validatedStartDate    AS validatedstartdate, ";
  $querySelect .= " pwe.plannedEndDate        AS plannedenddate, ";
  $querySelect .= " pwe.plannedStartDate      AS plannedstartdate, ";
  $querySelect .= " pwe.notPlannedWork        AS notplannedwork, ";
  $querySelect .= " pwe.assignedWork          AS assignedwork, ";
  $querySelect .= " pwe.validatedDuration     AS validatedduration, ";
  $querySelect .= " pwe.plannedDuration       AS plannedduration, ";
  $querySelect .= " pwe.idPlanningMode        AS idplanningmode, ";
  $querySelect .= " pwe.inheritedEndDate      AS inheritedenddate, ";
  $querySelect .= " pwe.surbooked             AS surbooked, ";
  $querySelect .= " pwe.color                 AS activitycolor, ";
}else if($typeKanbanC == 'Action' or $typeKanbanC == 'Requirement'){
  $querySelect .= " obj.actualDueDate         AS plannedenddate, ";
  $querySelect .= " NULL                      AS validatedenddate, ";
  $querySelect .= " NULL                      AS validatedstartdate, ";
  $querySelect .= " NULL                      AS plannedstartdate, ";
  $querySelect .= " NULL                      AS notplannedwork, ";
  $querySelect .= " NULL                      AS assignedwork, ";
  $querySelect .= " NULL                      AS validatedduration, ";
  $querySelect .= " NULL                      AS plannedduration, ";
  $querySelect .= " NULL                      AS idplanningmode, ";
  $querySelect .= " NULL                      AS inheritedenddate, ";
  $querySelect .= " NULL                      AS surbooked, ";
  $querySelect .= " NULL                      AS activitycolor, ";
}else if($typeKanbanC == 'Ticket'){
  $querySelect .= " obj.actualDueDateTime     AS plannedenddate, ";
  $querySelect .= " NULL                      AS validatedenddate, ";
  $querySelect .= " NULL                      AS validatedstartdate, ";
  $querySelect .= " NULL                      AS plannedstartdate, ";
  $querySelect .= " NULL                      AS notplannedwork, ";
  $querySelect .= " NULL                      AS assignedwork, ";
  $querySelect .= " NULL                      AS validatedduration, ";
  $querySelect .= " NULL                      AS plannedduration, ";
  $querySelect .= " NULL                      AS idplanningmode, ";
  $querySelect .= " NULL                      AS inheritedenddate, ";
  $querySelect .= " NULL                      AS surbooked, ";
  $querySelect .= " NULL                      AS activitycolor, ";
}else{
  $querySelect .= " NULL                      AS plannedenddate, ";
  $querySelect .= " NULL                      AS validatedenddate, ";
  $querySelect .= " NULL                      AS validatedstartdate, ";
  $querySelect .= " NULL                      AS plannedstartdate, ";
  $querySelect .= " NULL                      AS notplannedwork, ";
  $querySelect .= " NULL                      AS assignedwork, ";
  $querySelect .= " NULL                      AS validatedduration, ";
  $querySelect .= " NULL                      AS plannedduration, ";
  $querySelect .= " NULL                      AS idplanningmode, ";
  $querySelect .= " NULL                      AS inheritedenddate, ";
  $querySelect .= " NULL                      AS surbooked, ";
  $querySelect .= " NULL                      AS activitycolor, ";
}

if($hasVote){
  $querySelect .= " vti.locked                AS votelocked, ";
  $querySelect .= " vti.pctRate               AS votepctrate, ";
  
  // ---- Sous-requête : voteexist ----
  $votingTable    = $votingObj->getDatabaseTableName();
  $affTable       = $aff->getDatabaseTableName();
  $currentUserId  = getCurrentUserId();
  
  $querySelect .= " (SELECT COUNT(vtg.id) FROM $votingTable vtg
                     WHERE vtg.refType = '$typeKanbanC'
                       AND vtg.refId   = obj.id
                       AND (
                             vtg.idUser   = ".Sql::fmtId($currentUserId)."
                          OR vtg.idClient = (
                               SELECT aff2.idClient FROM $affTable aff2
                               WHERE aff2.id = ".Sql::fmtId($currentUserId)."
                                 AND aff2.isContact = '1'
                                 AND aff2.idClient IS NOT NULL
                               LIMIT 1
                             )
                           )
                   ) AS voteexist_raw, ";
  
  // ---- Sous-requête : canvote ----
  $votingAttrTable = $votingAttrObj->getDatabaseTableName();
  $querySelect .= " (SELECT COUNT(va.id) FROM $votingAttrTable va
                     WHERE va.idUser = ".Sql::fmtId($currentUserId)."
                       AND (va.refType IS NULL OR va.refType = '$typeKanbanC')
                       AND (va.idProject IS NULL OR va.idProject = obj.idProject)
                   ) AS canvote_user, ";
  
  $querySelect .= " (SELECT COUNT(va2.id) FROM $votingAttrTable va2
                     WHERE va2.idClient = (
                               SELECT aff_c.idClient FROM $affTable aff_c
                               WHERE aff_c.id = ".Sql::fmtId($currentUserId)."
                                 AND aff_c.isContact = '1'
                                 AND aff_c.idClient IS NOT NULL
                               LIMIT 1
                             )
                       AND va2.idClient IS NOT NULL
                       AND (va2.refType IS NULL OR va2.refType = '$typeKanbanC')
                       AND (va2.idProject IS NULL OR va2.idProject = obj.idProject)
                   ) AS canvote_client, ";
  
  // ---- Sous-requête : voteidrule ----
  $vurTable    = $votingUseRuleObj->getDatabaseTableName();
  $typeColName = 'id'.$typeKanbanC.'Type';
  
  $querySelect .= " COALESCE(
       (SELECT vur1.id FROM $vurTable vur1
        WHERE vur1.refType = '$typeKanbanC'
          AND vur1.idProject = obj.idProject
          AND vur1.idType    = obj.$typeColName
        LIMIT 1),
       (SELECT vur2.id FROM $vurTable vur2
        WHERE vur2.refType   = '$typeKanbanC'
          AND vur2.idProject  = obj.idProject
          AND vur2.idType     IS NULL
        LIMIT 1),
       (SELECT vur3.id FROM $vurTable vur3
        WHERE vur3.refType   = '$typeKanbanC'
          AND vur3.idProject  IS NULL
          AND vur3.idType     = obj.$typeColName
        LIMIT 1),
       (SELECT vur4.id FROM $vurTable vur4
        WHERE vur4.refType   = '$typeKanbanC'
          AND vur4.idProject  IS NULL
          AND vur4.idType     IS NULL
        LIMIT 1)
     )                        AS voteidrule_raw, ";
  
}else{
  $querySelect .= " NULL                      AS votelocked, ";
  $querySelect .= " NULL                      AS votepctrate, ";
  $querySelect .= " NULL                      AS voteexist_raw, ";
  $querySelect .= " NULL                      AS canvote_user, ";
  $querySelect .= " NULL                      AS canvote_client, ";
  $querySelect .= " NULL                      AS voteidrule_raw, ";
}

$querySelect .= " obj.description             AS description, ";
$querySelect .= " obj.idResource              AS idresource, ";
$querySelect .= " ty.code                     AS typecode, ";
$querySelect .= " ty.name                     AS typename, ";
$querySelect .= " ty.color                    AS typecolor, ";
$querySelect .= " st.name                     AS statusname, ";
$querySelect .= " st.color                    AS statuscolor, ";
$querySelect .= " st.isCopyStatus             AS iscopystatus, ";
$querySelect .= " p.name                      AS projectname, ";
$querySelect .= " p.color                     AS projectcolor, ";
$querySelect .= " aff.fullName                AS resourcename, ";

$querySelect .= " COUNT(n.id)                 AS notecount ";

// ====== FROM ======
$queryFrom  = $obj->getDatabaseTableName(). " obj ";
$queryFrom .= " LEFT JOIN ".$pwe->getDatabaseTableName()." pwe ON pwe.refType = '".$typeKanbanC."' AND pwe.refId = obj.id ";
$queryFrom .= " LEFT JOIN ".$ty->getDatabaseTableName()." ty ON ty.id = obj.id$typeClass ";
$queryFrom .= " LEFT JOIN ".$p->getDatabaseTableName()." p ON p.id = obj.idProject ";
$queryFrom .= " LEFT JOIN ".$st->getDatabaseTableName()." st ON st.id = obj.idStatus ";
$queryFrom .= " LEFT JOIN ".$aff->getDatabaseTableName()." aff ON aff.id = obj.idResource ";
if($hasActivity){
  $queryFrom .= " LEFT JOIN ".$act->getDatabaseTableName()." act ON act.id = obj.idActivity ";
}
if($hasPriority){
  $queryFrom .= " LEFT JOIN ".$prio->getDatabaseTableName()." prio ON prio.id = obj.idPriority ";
}
if($hasUrgency){
  $queryFrom .= " LEFT JOIN ".$urg->getDatabaseTableName()." urg ON urg.id = obj.idUrgency ";
}
if($hasVersion){
  $queryFrom .= " LEFT JOIN ".$tpv->getDatabaseTableName()." tpv ON tpv.id = obj.".$obj->getDatabaseColumnName('idTargetProductVersion')." ";
}
if($hasVote){
  $queryFrom .= " LEFT JOIN ".$vti->getDatabaseTableName()." vti ON vti.refType = '".$typeKanbanC."' AND vti.refId = obj.id ";
}
$queryFrom .= " LEFT JOIN ".$n->getDatabaseTableName()." n ON n.refType = '".$typeKanbanC."' AND n.refId = obj.id AND n.idle = '0' ";

// ====== WHERE ======
$queryWhere = "";

// Gestion du WHERE selon le type de colonne et le rafraîchissement
if($type == 'Status'){
  // Pour Status avec workflow - Récupération de tous les statuts du workflow
  $workflowStatus = new WorkflowStatus();
  $tableName2 = $workflowStatus->getDatabaseTableName();
  $typeObj = new Type();
  $tableName3 = $typeObj->getDatabaseTableName();
  $statusObj = new Status();
  $tableName = $statusObj->getDatabaseTableName();
  
  // Récupérer tous les statuts du workflow dans l'ordre
  $queryAllStatus = "SELECT s.id, s.sortOrder
                     FROM $tableName s
                     WHERE (idle = '0' or isCopyStatus = '1') AND (s.id IN (SELECT idStatusFrom FROM $tableName2 w, $tableName3 t
                                   WHERE t.idWorkflow=w.idWorkflow AND t.scope='$typeKanbanC')
                          OR s.id IN (SELECT idStatusTo FROM $tableName2 w, $tableName3 t
                                      WHERE t.idWorkflow=w.idWorkflow AND t.scope='$typeKanbanC'))
                     ORDER BY s.sortOrder";
  $resultAllStatus = Sql::query($queryAllStatus);
  $allStatusInOrder = array();
  $allCopyStatus = array();
  while($lineStatus = Sql::fetchLine($resultAllStatus)){
    $allStatusInOrder[] = $lineStatus['id'];
  }
  foreach ($backlogColumnList as $st){
    $status = new Status($st, true);
    if($status->isCopyStatus){
      $allCopyStatus[] = $st;
    }
  }
  
  // Construire la liste des statuts à récupérer pour chaque colonne
  $statusToRetrieve = array();
  
  if($onlyRefreshBacklog){
    // Rafraîchir uniquement le backlog (statuts forAgileScrum = 0)
    $idCol = array_key_first($backlogColumnList);
    $fromIdx = array_search($columnRanges[$idCol]['from'], $allStatusInOrder);
    $toIdx = array_search($columnRanges[$idCol]['to'], $allStatusInOrder);
    if($fromIdx !== false && $toIdx !== false){
      for($i = $fromIdx; $i < $toIdx; $i++){
        $statusToRetrieve[] = $allStatusInOrder[$i];
      }
    }else if($fromIdx !== false){
      for($i = $fromIdx; $i < count($allStatusInOrder); $i++){
        $statusToRetrieve[] = $allStatusInOrder[$i];
      }
    }
    $statusToRetrieve = array_merge($statusToRetrieve, $allCopyStatus);
  }else if($onlyRefresh){
    // Rafraîchir uniquement les colonnes spécifiées
    foreach($arrayRefreshColumn as $colId){
      if(isset($columnRanges[$colId])){
        // Trouver tous les statuts entre from et to
        $fromIdx = array_search($columnRanges[$colId]['from'], $allStatusInOrder);
        if($columnRanges[$colId]['to'] !== null){
          $toIdx = array_search($columnRanges[$colId]['to'], $allStatusInOrder);
          if($fromIdx !== false && $toIdx !== false){
            for($i = $fromIdx; $i < $toIdx; $i++){
              $statusToRetrieve[] = $allStatusInOrder[$i];
            }
          }
        }else{
          // Dernière colonne - tous les statuts depuis from jusqu'à la fin
          if($fromIdx !== false){
            for($i = $fromIdx; $i < count($allStatusInOrder); $i++){
              $statusToRetrieve[] = $allStatusInOrder[$i];
            }
          }
        }
      }else if(in_array($colId, $backlogColumnList)){
        $statusToRetrieve[] = $colId;
      }
    }
  }else{
    // Charger toutes les colonnes
    foreach($columnRanges as $colId => $range){
      // Trouver tous les statuts entre from et to
      $fromIdx = array_search($range['from'], $allStatusInOrder);
      if($range['to'] !== null){
        $toIdx = array_search($range['to'], $allStatusInOrder);
        if($fromIdx !== false && $toIdx !== false){
          for($i = $fromIdx; $i < $toIdx; $i++){
            $statusToRetrieve[] = $allStatusInOrder[$i];
          }
        }
      }else{
        // Dernière colonne - tous les statuts depuis from jusqu'à la fin
        if($fromIdx !== false){
          for($i = $fromIdx; $i < count($allStatusInOrder); $i++){
            $statusToRetrieve[] = $allStatusInOrder[$i];
          }
        }
      }
    }
    // Ajouter le backlog si nécessaire
    if($refreshBacklog){
      $statusToRetrieve = array_merge($statusToRetrieve, $backlogColumnList);
    }
  }
  
  // Créer la clause WHERE avec tous les statuts
  $statusToRetrieve = array_unique($statusToRetrieve);
  foreach ($statusToRetrieve as $key=>$idStatus){
    $isHidedStatus = Parameter::getUserParameter('kanbanColumnStatusHide_'.$idKanban.'_'.$idStatus);
    $isHidedStatus = ($isHidedStatus == '1')?true:false;
    if($isHidedStatus){
      unset($statusToRetrieve[$key]);
      continue;
    }
  }
  
  if(count($statusToRetrieve) > 0){
    $queryWhere = "obj.idStatus IN (0, ".implode(',', $statusToRetrieve).") ";
  }else{
    $queryWhere = " 1=1 ";
  }
  
  // Masquer le backlog si nécessaire
  if($hideBacklog == 'off' or $hideBacklog == '0'){
    // Exclure uniquement les statuts du backlog qui ne sont pas aussi récupérés
    $backlogOnly = array_diff($backlogColumnList, $statusToRetrieve);
    $queryWhere .= " AND obj.idStatus != 0 ";
    if(count($backlogOnly) > 0){
      $queryWhere .= " AND obj.idStatus NOT IN (".implode(',', $backlogOnly).") ";
    }
  }

}else{
  // Pour les autres types sans workflow (Sprint, TargetProductVersion, Activity, Milestone)
  if($onlyRefreshBacklog){
    // Rafraîchir uniquement le backlog (valeur NULL ou non dans les colonnes actives)
    $activeColumns = array_diff($columnList, array($idBacklogColumn));
    if(count($activeColumns) > 0){
      $queryWhere = "( obj.".$obj->getDatabaseColumnName($columnField)." IS NULL OR obj.".$obj->getDatabaseColumnName($columnField)." NOT IN (".implode(',', $activeColumns).") ) ";
    }else{
      $queryWhere = "( obj.".$obj->getDatabaseColumnName($columnField)." IS NULL OR obj.".$obj->getDatabaseColumnName($columnField)." = 0 ) ";
    }
  }else if($onlyRefresh){
    // Rafraîchir uniquement les colonnes spécifiées
    $queryWhere = "( obj.".$obj->getDatabaseColumnName($columnField)." IN (0, ".implode(',', $arrayRefreshColumn).") ";
    if($refreshBacklog){
      $queryWhere .= " OR obj.".$obj->getDatabaseColumnName($columnField)." IS NULL ";
    }
    $queryWhere .= " ) ";
  }else{
    // Charger toutes les colonnes
    if(count($columnList) > 0){
      $queryWhere = "( obj.".$obj->getDatabaseColumnName($columnField)." IN (".implode(',', $columnList).") ";
      if($refreshBacklog){
        $queryWhere .= " OR obj.".$obj->getDatabaseColumnName($columnField)." IS NULL ";
      }
      $queryWhere .= " ) ";
    }else{
      $queryWhere = " 1=1 ";
    }
  }
  
  // Masquer le backlog si nécessaire
  if($hideBacklog == 'off' or $hideBacklog == '0'){
    $queryWhere .= " AND obj.".$obj->getDatabaseColumnName($columnField)." IS NOT NULL ";
  }
}

// Filtres communs
$queryWhere .= " AND obj.idProject IN ".getVisibleProjectsList();
if($typeKanbanC == 'Requirement' and getSessionValue('project') == '*'){
  $queryWhere .= " OR obj.idProject IS NULL ";
}
$showIdle = ($showIdle == 'on' or $showIdle == '1')?true:false;
$queryWhere .= (!$showIdle) ? " AND obj.idle = '0' " : " ";
if($typeKanbanC == 'Activity' and ($hideParentActivities == 'on' or $hideParentActivities == '1')){
  $queryWhere .= " AND pwe.elementary = '1' ";
}

// ====== FILTRES UTILISATEUR ======
$arrayFilter = array();
if(isset(getSessionUser()->_arrayFilters[$typeKanbanC]) && is_array(getSessionUser()->_arrayFilters[$typeKanbanC])){
  $arrayFilter = getSessionUser()->_arrayFilters[$typeKanbanC];
}

$queryOrderBy = '';
$idTab = 0;

foreach ($arrayFilter as $i => $crit) {
  if (pq_trim($crit['sql']['operator'])=='exists') {
    $crit['sql']['attribute']=null;
  }
  if ($crit['sql']['operator']!='SORT') { // Sorting already applied above
    $split=pq_explode('_', $crit['sql']['attribute']);
    if (pq_strpos($crit['sql']['attribute'], '__id')>0) $split=array();
    $critSqlValue=$crit['sql']['value'];
    
    // Dynamic filter
    if (pq_array_key_exists('isDynamic', $crit) and $crit['isDynamic']=='1' and ($crit['sql']['operator']=='IN' or $crit['sql']['operator']=='NOT IN' or pq_strpos($crit['sql']['operator'],'LIKE')!==false)) {
      if ($crit['sql']['value']==0) continue;
    }
    if (pq_array_key_exists('isDynamic', $crit) and $crit['isDynamic']=='1' and $crit['sql']['value']=='bool') continue;
    
    // Work
    if (pq_substr($crit['sql']['attribute'], -4, 4) == 'Work' and pq_substr($critSqlValue,0,1)!='[') {
      if ($typeKanbanC=='Ticket') {
        $critSqlValue=Work::convertImputation(pq_trim($critSqlValue,"'"));
      } else {
        $critSqlValue=Work::convertWork(pq_trim($critSqlValue,"'"));
      }
    }
    
    if ($crit['sql']['operator']=='IN'
        and ($crit['sql']['attribute']=='idProduct' or $crit['sql']['attribute']=='idProductOrComponent' or $crit['sql']['attribute']=='idComponent')) {
          $critSqlValue=pq_str_replace(array(' ','(',')'), '', $critSqlValue);
          $splitVal=pq_explode(',',$critSqlValue);
          $critSqlValue='(0';
          foreach ($splitVal as $idP) {
            $prod=new Product($idP,true);
            $critSqlValue.=', '.$idP;
            $list=$prod->getRecursiveSubProductsFlatList(false, false); // Will work only if selected is Product, not for Component
            foreach ($list as $idPrd=>$namePrd) {
              $critSqlValue.=', '.$idPrd;
            }
          }
          $critSqlValue.=')';
        }
        
        // itemName
        if ($crit['sql']['attribute'] == 'itemName') {
          $queryWhere.=($queryWhere=='')?'':' and ';
          $queryWhere .= '(';
          $ass = new Assignment();
          $assTable = $ass->getDatabaseTableName();
          $queryRefTypes = Sql::query("SELECT DISTINCT refType FROM $assTable");
          $refTypes = [];
          $isPgSql = Sql::isPgsql();
          while ($row = Sql::fetchLine($queryRefTypes)) {
            if ($isPgSql){
              if (isset($row['reftype']) && !in_array($row['reftype'], $refTypes)) {
                if (class_exists($row['reftype'])) $refTypes[] = $row['reftype'];
              }
            }else{
              if (isset($row['refType']) && !in_array($row['refType'], $refTypes)) {
                if (class_exists($row['refType'])) $refTypes[] = $row['refType'];
              }
            }
          }
          $conditions = [];
          $operator = strtoupper(trim($crit['sql']['operator']));
          foreach ($refTypes as $refType) {
            $alias = strtoupper(substr($refType, 0, 2));
            $conditions[] = "(obj.refType = '$refType' AND $alias.name $operator " .$critSqlValue. ")";
          }
          if ($operator == 'IS NULL') {
            $refTypeList = "'" . implode("','", $refTypes) . "'";
            $conditions[] = "(obj.refType NOT IN ($refTypeList))";
          }
          $queryWhere .= implode(' OR ', $conditions) . ')';
          continue;
        }
        
        // indicatorFileNoteLink
        if ($crit['sql']['attribute'] == 'indicatorFileNoteLink') {
          $queryWhere.=($queryWhere=='')?'':' and ';
          $aff=new Affectable(getSessionUser()->id,true);
          $idTeamCurrentUser = $aff->idTeam;
          $userId = getSessionUser()->id;
          $note = new Note();
          $noteTable = $note->getDatabaseTableName();
          $link = new Link();
          $linkTable = $link->getDatabaseTableName();
          $attachment = new Attachment();
          $attachmentTable = $attachment->getDatabaseTableName();
          $operator = strtoupper(trim($crit['sql']['operator']));
          $nullOrNot = ($operator == 'IS NULL') ? '=' : '>';
          $andOr = ($operator == 'IS NULL') ? 'AND' : 'OR';
          $isNullIsNotNull = ($operator == 'IS NULL' || $operator == 'IS NOT NULL') ? true : false;
          $queryWhere.='(';
          if ($operator == 'HASNOTES' || $isNullIsNotNull){
            $queryWhere .= '((SELECT COUNT(n.id) FROM '.$noteTable.' n WHERE n.refType = \'' . $typeKanbanC . '\' AND n.refId = obj.id
                                  AND (n.idPrivacy=1 OR (n.idPrivacy=2 and n.idTeam=' . Sql::fmtId($idTeamCurrentUser) . ') OR (n.idPrivacy=3 and n.idUser=' . Sql::fmtId($userId) . '))) ' . $nullOrNot . ' 0) ';
            if ($isNullIsNotNull) $queryWhere .= $andOr;
          }
          if ($operator == 'HASATTACHMENTS' || $isNullIsNotNull){
            $queryWhere .= '((SELECT COUNT(a.id) FROM '.$attachmentTable.' a WHERE a.refType = \'' . $typeKanbanC . '\' AND a.refId = obj.id
                                  AND (a.idPrivacy=1 OR (a.idPrivacy=2 and a.idTeam=' . Sql::fmtId($idTeamCurrentUser) . ') OR (a.idPrivacy=3 and a.idUser=' . Sql::fmtId($userId) . '))) ' . $nullOrNot . ' 0) ';
            if ($isNullIsNotNull) $queryWhere .=  $andOr;
          }
          if ($operator == 'HASLINKS' || $isNullIsNotNull){
            $queryWhere .= '((SELECT COUNT(l.id) FROM '.$linkTable.' l WHERE (l.ref1Type = \'' . $typeKanbanC . '\' AND l.ref1Id = obj.id
                                  OR l.ref2Type = \'' . $typeKanbanC . '\' AND l.ref2Id = obj.id)) ' . $nullOrNot .' 0) ';
          }
          $queryWhere.=')';
          continue;
        }
        
        if (count($split)>1 ) {
          $externalClass=$split[0];
          $externalObj=new $externalClass();
          $externalTable = $externalObj->getDatabaseTableName();
          $idTab+=1;
          $externalTableAlias = 'T' . $idTab;
          $queryFrom .= ' left join ' . $externalTable . ' as ' . $externalTableAlias .
          ' on ( ' . $externalTableAlias . ".refType='" . get_class($obj) . "' and " .  $externalTableAlias . '.refId = obj.id )';
          $queryWhere.=($queryWhere=='')?'':' and ';
          
          $extField=$externalObj->getDatabaseColumnName($split[1]);
          $testField=pq_str_replace(array($externalClass.'_','[',']'),'',$critSqlValue);
          $isPgSql = Sql::isPgsql();
          
          //arithmetic expressions of the type ‘[field] +2’
          if (preg_match('/^([A-Za-z_][A-Za-z0-9_]*)\s*([+\-x])\s*(\d+(?:\.\d+)?)$/', $testField, $matches)){
            $fieldName = $matches[1];
            $operatorCompare = $matches[2];
            if ($operatorCompare =="x") $operatorCompare='*';
            $filterCompareValue = $matches[3];
            if (substr($crit['sql']['attribute'], -4) === "Date" || substr($crit['sql']['attribute'], -8) === "DateTime") {
              if ($isPgSql) $queryWhere .= $externalTableAlias . "." . $extField. " " . $crit['sql']['operator'] . " ". $externalTableAlias . "." . $fieldName . " ". $operatorCompare . " INTERVAL '" . $filterCompareValue . " day'";
              else $queryWhere .= $externalTableAlias . "." . $extField. " " . $crit['sql']['operator'] . " ". $externalTableAlias . "." . $fieldName . " ". $operatorCompare . " INTERVAL " . $filterCompareValue . " DAY";
            } else {
              $queryWhere .= $externalTableAlias . "." . $extField. " " . $crit['sql']['operator'] . " ". $externalTableAlias . "." . $fieldName . " ". $operatorCompare . " " . $filterCompareValue;
            }
          }
          // "[ClassName_field]"
          else if ($critSqlValue=='['.$externalClass.'_'.$testField.']') {
            $queryWhere.=$externalTableAlias.".".$extField.' '.$crit['sql']['operator']." $externalTableAlias.$testField";
          }else if ($critSqlValue=='['.$testField.']') {
            $queryWhere.=$externalTableAlias.".".$extField.' '.$crit['sql']['operator']." obj.$testField";
          }else if ($crit['sql']['operator']=='=month+' or $crit['sql']['operator']=='=year+'){
            $queryWhere.=$externalTableAlias.".".$extField.' '.$critSqlValue;
          }else{
            $queryWhere.=$externalTableAlias.".".$extField.' '.$crit['sql']['operator'].' '.$critSqlValue;
          }
        } else {
          $queryWhere.=($queryWhere=='')?'':' and ';
          if ($crit['sql']['operator']!=' exists ') {
            $queryWhere.="(obj." . $crit['sql']['attribute'] . ' ';
          }
          
          $testField=pq_str_replace(array('[',']'),'',$critSqlValue);
          if ($crit['sql']['operator']=='=month+' or $crit['sql']['operator']=='=year+') {
            $queryWhere.=$critSqlValue;
          }else if ($critSqlValue=="[$testField]"){
            $queryWhere.=$crit['sql']['operator']." obj.$testField";
          }else {
            $queryWhere.=$crit['sql']['operator'] . ' ' . $critSqlValue;
          }
          
          if (pq_strlen($crit['sql']['attribute'])>=9
              and pq_substr($crit['sql']['attribute'],0,2)=='id'
              and ( pq_substr($crit['sql']['attribute'],-7)=='Version' and SqlElement::is_a(pq_substr($crit['sql']['attribute'],2), 'Version') )
              and $crit['sql']['operator']=='IN') {
                $scope=pq_substr($crit['sql']['attribute'],2);
                $vers=new OtherVersion();
                $queryWhere.=" or exists (select 'x' from ".$vers->getDatabaseTableName()." VERS "
                    ." where VERS.refType=".Sql::str($typeKanbanC)." and VERS.refId=obj.id and scope=".Sql::str($scope)
                    ." and VERS.idVersion IN ".$critSqlValue
                    .")";
              }
              if ($crit['sql']['operator']=='NOT IN') {
                $queryWhere.=" or obj." . $crit['sql']['attribute']. " IS NULL ";
              }
              if ($crit['sql']['operator']!=' exists ') {
                $queryWhere.=")";
              }
        }
  }
}

// ====== FILTRES DE TRI ======
foreach ($arrayFilter as $crit) {
  if ($crit['sql']['operator']=='SORT') {
    $doneSort=false;
    $split=pq_explode('_', $crit['sql']['attribute']);
    if (count($split)>1 ) {
      $externalClass=$split[0];
      $externalObj=new $externalClass();
      $externalTable = $externalObj->getDatabaseTableName();
      $idTab+=1;
      $externalTableAlias = 'T' . $idTab;
      $queryFrom .= ' left join ' . $externalTable . ' as ' . $externalTableAlias .
      ' on ( ' . $externalTableAlias . ".refType='" . get_class($obj) . "' and " .  $externalTableAlias . '.refId = obj.id )';
      $queryOrderBy .= ($queryOrderBy=='')?'':', ';
      $queryOrderBy .= " " . $externalTableAlias . '.' . $split[1]
      . " " . $crit['sql']['value'];
      $doneSort=true;
    }
    if (pq_substr($crit['sql']['attribute'],0,2)=='id' and pq_strlen($crit['sql']['attribute'])>2 ) {
      $externalClass = pq_substr($crit['sql']['attribute'],2);
      $externalObj=new $externalClass();
      $externalTable = $externalObj->getDatabaseTableName();
      $sortColumn='id';
      if (property_exists($externalObj,'sortOrder')) {
        $sortColumn=$externalObj->getDatabaseColumnName('sortOrder');
      } else {
        $sortColumn=$externalObj->getDatabaseColumnName('name');
      }
      $idTab+=1;
      $externalTableAlias = 'T' . $idTab;
      $queryOrderBy .= ($queryOrderBy=='')?'':', ';
      $queryOrderBy .= " " . $externalTableAlias . '.' . $sortColumn
      . " " . pq_str_replace("'","",$crit['sql']['value']);
      $queryFrom .= ' left join ' . $externalTable . ' as ' . $externalTableAlias .
      ' on ' . "obj." . $obj->getDatabaseColumnName('id' . $externalClass) .
      ' = ' . $externalTableAlias . '.' . $externalObj->getDatabaseColumnName('id');
      $doneSort=true;
    }
    if (! $doneSort) {
      $queryOrderBy .= ($queryOrderBy=='')?'':', ';
      $queryOrderBy .= " obj." . $obj->getDatabaseColumnName($crit['sql']['attribute'])
      . " " . $crit['sql']['value'];
    }
  }
}

// ====== GESTION DU TRI ======
$orderBySql = "";
switch ($orderBy) {
  case 'id':
    $orderBySql = " obj.id ASC";
    break;
  case 'name':
    $orderBySql = " obj.name ASC";
    break;
  case 'idpriority':
    if($typeKanbanC == 'Activity'){
      $orderBySql = " pwe.priority ASC";
    }else{
      $orderBySql = " prio.value DESC";
    }
    break;
  case 'idstatus':
    $orderBySql = " st.sortOrder ASC ";
    break;
  case 'idresponsible':
    $orderBySql = " aff.fullName ASC";
    break;
  case 'idtargetproductversion':
    $orderBySql = " tpv.name ASC ";
    break;
  case 'validatedenddate':
    $orderBySql = " pwe.validatedEndDate ASC ";
    break;
  default:
    $orderBySql = " obj.id ASC";
}

// ====== GROUP BY ======
$queryGroupBy  = " obj.id, obj.name, obj.id".$typeKanbanC."Type, ";
$queryGroupBy .= " obj.idStatus, obj.idProject, ";
$queryGroupBy .= " obj.".$obj->getDatabaseColumnName($columnField).", ";

if($hasUrgency){
  $queryGroupBy .= " obj.idUrgency, urg.name, urg.color, ";
}

if($hasPriority){
  $queryGroupBy .= " obj.idPriority, prio.name, prio.color, ";
}

if($hasVersion){
  $queryGroupBy .= " obj.".$obj->getDatabaseColumnName('idTargetProductVersion').", tpv.name, ";
}

if($hasMilestone){
  $queryGroupBy .= " obj.idMilestone, ";
}

if($hasActivity){
  $queryGroupBy .= " obj.idActivity, act.name, ";
}

if($hasWorkElement){
  $queryGroupBy .= " pwe.plannedWork, pwe.realWork, pwe.leftWork, ";
}

if($hasVote){
  $queryGroupBy .= " vti.locked, vti.pctRate, ";
}


if($typeKanbanC == 'Activity' and $hasWorkElement){
  $queryGroupBy .= " pwe.validatedEndDate, pwe.validatedStartDate, ";
  $queryGroupBy .= " pwe.plannedEndDate, pwe.plannedStartDate, ";
  $queryGroupBy .= " pwe.notPlannedWork, pwe.assignedWork, ";
  $queryGroupBy .= " pwe.validatedDuration, pwe.plannedDuration, ";
  $queryGroupBy .= " pwe.idPlanningMode, pwe.inheritedEndDate, pwe.surbooked, pwe.color, ";
}else if($typeKanbanC == 'Action' or $typeKanbanC == 'Requirement'){
  $queryGroupBy .= " obj.actualDueDate, ";
}else if($typeKanbanC == 'Ticket'){
  $queryGroupBy .= " obj.actualDueDateTime, ";
}

$queryGroupBy .= " obj.description, obj.idResource, ";
$queryGroupBy .= " ty.code, ty.name, ty.color, ";
$queryGroupBy .= " st.name, st.color, st.isCopyStatus, st.sortOrder, ";
$queryGroupBy .= " p.name, p.color, ";
$queryGroupBy .= " aff.fullName ";

switch ($orderBy) {
  case 'idpriority':
    if($typeKanbanC == 'Activity'){
      $queryGroupBy .= " ,pwe.priority";
    }else{
      $queryGroupBy .= " ,prio.value";
    }
    break;
  case 'idtargetproductversion':
    $queryGroupBy .= " ,tpv.name ";
    break;
  case 'validatedenddate':
    $queryGroupBy .= " ,pwe.validatedEndDate ";
    break;
}

// ====== ORDER BY ======
$finalOrderBy = '';
if($queryOrderBy != '' || $orderBy != ''){
  if(pq_strpos($queryOrderBy, '.wbs') !== false){
    $queryOrderBy = pq_str_replace('.wbs', '.wbsSortable', $queryOrderBy);
  }
  if($orderBySql != '' && $queryOrderBy != ''){
    $finalOrderBy = " ORDER BY $orderBySql, $queryOrderBy ";
  } else {
    $finalOrderBy = " ORDER BY $orderBySql $queryOrderBy ";
  }
}

// ====== REQUÊTE FINALE ======
$query  = "SELECT ".$querySelect;
$query .= " FROM ".$queryFrom;
$query .= " WHERE ".$queryWhere;
$query .= " GROUP BY ".$queryGroupBy;
$query .= $finalOrderBy;
$result = Sql::query($query);

// ============================================================================
// TRAITEMENT DES RÉSULTATS
// ============================================================================
$jsonItemList = array();
while($line = Sql::fetchLine($result)){
  
  // Détermination de la colonne
  $idColumn = $line['columnvalue'];
  if(!$idColumn or $idColumn == '0'){
    $idColumn = $idBacklogColumn;
  }
  
  // Détermination du type DND
  $dndType = $idColumn;
  if($type != 'Status' && $type != 'TargetProductVersion'){
    $dndType = $line['idproject'];
  }
  
  $key = $type.'_'.$idColumn.'_'.$typeKanbanC.'_'.$line['id'];
  
  $jsonItemList[$key] = array();
  
  $jsonItemList[$key]['id']             = $key;
  $jsonItemList[$key]['dndtype']        = 'column'.$dndType;
  $jsonItemList[$key]['name']           = htmlEncode(pq_htmlspecialchars($line['name']));
  $jsonItemList[$key]['reftype']        = $typeKanbanC;
  $jsonItemList[$key]['iconclass']      = $typeKanbanC;
  $jsonItemList[$key]['refid']          = $line['id'];
  $jsonItemList[$key]['idtype']         = $line['idtype'];
  
  // type
  $typename = $line['typecode'];
  if(!$typename){
    $typename = pq_substr(ucfirst($line['typename']), 0, 3);
  }
  $jsonItemList[$key]['typename'] = htmlEncode(pq_htmlspecialchars($typename));
  $jsonItemList[$key]['typecolor'] = $line['typecolor'];
  
  // projet
  $jsonItemList[$key]['idproject']    = $line['idproject'];
  $jsonItemList[$key]['projectname']  = htmlEncode(pq_htmlspecialchars($line['projectname']));
  $jsonItemList[$key]['projectcolor'] = $line['projectcolor'] ? $line['projectcolor'] : '#777777';
  
  // statut
  $jsonItemList[$key]['idstatus']    = $line['idstatus'];
  $jsonItemList[$key]['statusname']  = htmlEncode(pq_htmlspecialchars($line['statusname']));
  $jsonItemList[$key]['statuscolor'] = $line['statuscolor'];
  $jsonItemList[$key]['statustextcolor'] = htmlForeColorForBackgroundColor($line['statuscolor']);
  $jsonItemList[$key]['isstatusccolorlight'] = htmlIsLightColor($line['statuscolor']);
  $jsonItemList[$key]['iscopystatus'] = $line['iscopystatus'];
  $ws=new WorkflowStatus();
  $profile = getSessionUser()->getProfile();
  $crit=array('idWorkflow'=>'0', 'allowed'=>1, 'idProfile'=>$profile, 'idStatusFrom'=>'1');
  $wsList=$ws->getSqlElementsFromCriteria($crit, false);
  $next = 1;
  if(count($wsList)>0){
    $next=$wsList[0]->id;
  }
  $jsonItemList[$key]['idcopystatusnext'] = $next;
  $jsonItemList[$key]['copystatusnextname'] = htmlEncode(pq_htmlspecialchars(SqlList::getNameFromId('Status', $next)));
  
  // urgency
  $jsonItemList[$key]['idurgency'] = $line['idurgency'];
  $jsonItemList[$key]['urgencyname']  = htmlEncode(pq_htmlspecialchars($line['urgencyname']));
  $jsonItemList[$key]['urgencycolor'] = $line['urgencycolor'];
  
  // priority
  $jsonItemList[$key]['idpriority'] = $line['idpriority'];
  $jsonItemList[$key]['priorityname']  = htmlEncode(pq_htmlspecialchars($line['priorityname']));
  $jsonItemList[$key]['prioritycolor'] = $line['prioritycolor'];
  
  // responsable
  $jsonItemList[$key]['idresource'] = $line['idresource'];
  if($line['idresource']){
    $file     = Affectable::getThumbUrl('Affectable', $line['idresource'], 32);
    $username = pq_htmlspecialchars($line['resourcename']);
    
    if(pq_substr($file, 0, 6) == 'letter'){
      $isfile          = false;
      $responsibleicon = pq_strtoupper(pq_mb_substr($username, 0, 1, 'UTF-8'));
    }else{
      $isfile          = true;
      $responsibleicon = $file;
    }
    
    $usernametitle = $username.'<br/><span style=font-size:80%><i>('.i18n('colResponsible').')</i></span>';
    
    $jsonItemList[$key]['responsible'] = array(
        'isfile'    => $isfile,
        'file'      => htmlEncode($responsibleicon),
        'name'      => htmlEncode($username),
        'nametitle' => htmlEncode($usernametitle)
    );
  }else{
    $jsonItemList[$key]['responsible'] = '';
  }
  
  // version produit cible
  $jsonItemList[$key]['idtargetproductversion']   = $line['idtargetproductversion'];
  $jsonItemList[$key]['targetproductversionname'] = htmlEncode(pq_htmlspecialchars($line['targetproductversionname']));
  
  // activity
  $jsonItemList[$key]['idactivity'] = $line['idactivity'];
  $jsonItemList[$key]['activityname']  = htmlEncode(pq_htmlspecialchars($line['activityname']));
  $jsonItemList[$key]['activitycolor']  = $line['activitycolor'];
  
  // work
  $jsonItemList[$key]['plannedwork'] = Work::displayWork(floatval($line['plannedwork']), 2);
  $jsonItemList[$key]['realwork']    = Work::displayWork(floatval($line['realwork']), 2);
  $jsonItemList[$key]['leftwork']    = Work::displayWork(floatval($line['leftwork']), 2);
  $jsonItemList[$key]['workunit']    = Work::displayShortWorkUnit();
  
  // planned date avec couleur pour Activity
  if($typeKanbanC == 'Activity'){
    $pColor = '#50BB50';
    $pColorBlindColor = $pColor;
    if($line['notplannedwork'] > 0){
      $pColor = '#9933CC';
      $pColorBlindColor = '#BB5050';
    }else if(pq_trim($line['validatedenddate']) != "" and $line['validatedenddate'] < $line['plannedenddate']){
      if($typeKanbanC != 'Milestone' and (!$line['assignedwork'] or $line['assignedwork'] == 0) and (!$line['leftwork'] or $line['leftwork'] == 0) and (!$line['realwork'] or $line['realwork'] == 0)){
        $pColor = '#BB9099';
        $pColorBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
      }else{
        $pColor = '#BB5050';
        $pColorBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
      }
    }else if((($line['idplanningmode'] == 8 or $line['idplanningmode'] == 14) and intval($line['validatedduration']) < intval($line['plannedduration']))
        or (($line['idplanningmode'] == 25 or $line['idplanningmode'] == 26) and $line['plannedstartdate'] != $line['validatedstartdate'])
        or (($line['idplanningmode'] == 19 or $line['idplanningmode'] == 21) and $line['plannedstartdate'] < $line['validatedstartdate'])){
          $pColor = '#BB5050';
          $pColorBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
    }else if($typeKanbanC != 'Milestone' and (!$line['assignedwork'] or $line['assignedwork'] == 0) and (!$line['leftwork'] or $line['leftwork'] == 0) and (!$line['realwork'] or $line['realwork'] == 0)){
      $pColor = '#AEC5AE';
    }
    if($line['surbooked'] == 1){
      $pColor = '#f4bf42';
      $pColorBlindColor = '#bfbfbf';
    }
    // Color for late from inheritedEndDate
    if(pq_trim($line['validatedenddate']) == "" and pq_trim($line['inheritedenddate']) != "" and $line['inheritedenddate'] < $line['plannedenddate']){
      if($line['assignedwork'] > 0) $pColor = '#DA70D6';
      else $pColor = '#DDA0DD';
    }
    $jsonItemList[$key]['planneddatecolor'] = ($isColorBlind) ? $pColorBlindColor : $pColor;
  }else{
    $pColor = '#F1F1F1';
    $pColorBlindColor = $pColor;
    $jsonItemList[$key]['planneddatecolor'] = ($isColorBlind) ? $pColorBlindColor : $pColor;
  }
  $plannedDate = date('Y-m-d', pq_strtotime($line['plannedenddate']));
  $jsonItemList[$key]['planneddate'] = htmlFormatDate($plannedDate);
  $jsonItemList[$key]['planneddatetextcolor'] = htmlForeColorForBackgroundColor($jsonItemList[$key]['planneddatecolor']);
  $jsonItemList[$key]['plannedtextcolor'] = htmlForeColorForPlannedColor($jsonItemList[$key]['planneddatecolor']);
  
  // title
  $titleColor = '';
  if ($hideColorTitle == 'on' or $hideColorTitle == '1'){
    if($modeColorTitle=='colorProject'){
      $titleColor = $jsonItemList[$key]['projectcolor'];
    }else if ($modeColorTitle=='colorItem'){
      $titleColor = $jsonItemList[$key]['activitycolor'];
    }else if($modeColorTitle=='colorPlanned'){
      $titleColor = $jsonItemList[$key]['planneddatecolor'];
    }else if($modeColorTitle=='colorType'){
      $titleColor = $jsonItemList[$key]['typecolor'];
    }else if($modeColorTitle=='colorPriority'){
      $titleColor = $jsonItemList[$key]['prioritycolor'];
    }else if($modeColorTitle=='colorUrgency'){
      $titleColor = $jsonItemList[$key]['urgencycolor'];
    }
  }
  $titleTextColor = getForeColor($titleColor);
  $useFullTileColor = (($hideColorTitle == 'on' or $hideColorTitle == '1') and ($colorOnTitleOrFullTile == 'on' or $colorOnTitleOrFullTile == '1') and $titleColor);
  
  $jsonItemList[$key]['titlecolor'] = $titleColor;
  $jsonItemList[$key]['titletextcolor'] = $titleTextColor;
  
  // description
  $description = $line['description'];
  if(!$description){
    $description = "<div style='font-style:italic; color:".(($useFullTileColor)?$titleTextColor:'#CDCADB').";'>".i18n('kanbanNoDescription')."</div>";
  }else{
    $description = pq_str_replace(
        '<img ',
        '<img style="max-width:100%" onclick="showImage(\'Note\',this.src,\' \');" ',
        $description
        );
    $description = pq_str_replace(
        '<div',
        "<div ".(($useFullTileColor)?"style='color:".$titleTextColor.";'" :''),
        $description
        );
  }
  $jsonItemList[$key]['description'] = htmlEncode(pq_htmlspecialchars($description));
  
  // nombre de notes
  $jsonItemList[$key]['notebadge'] = ($line['notecount'] > 0) ? $line['notecount'] : '';
  
  // votingItem (si propriété existe)
  if ($line['votelocked'] == '0')  {
    $canVote   = ($line['canvote_user'] > 0 || $line['canvote_client'] > 0) ? true : false;
    $voteExist = ($line['voteexist_raw'] > 0) ? true : false;
    $idRule    = $line['voteidrule_raw'];
    $jsonItemList[$key]['canvote'] = $canVote;
    $jsonItemList[$key]['voteexist'] = $voteExist;
    $jsonItemList[$key]['voteidrule'] = $idRule;
    $jsonItemList[$key]['votepctrate'] = $line['votepctrate'];
  }else{
    $jsonItemList[$key]['canvote'] = false;
    $jsonItemList[$key]['voteexist'] = false;
    $jsonItemList[$key]['voteidrule'] = '';
    $jsonItemList[$key]['votepctrate'] = '';
  }
  $jsonItemList[$key]['editortype'] = getEditorType();
  
  $jsonItemList[$key]['hidecolortitle'] = $hideColorTitle;
  $jsonItemList[$key]['modecolortitle'] = $modeColorTitle;
  $jsonItemList[$key]['colorontitleorfulltile'] = $colorOnTitleOrFullTile;
  
  // Ajout de l'item à la colonne appropriée
  // Gestion différente selon le type de colonne
  if($type == 'Status'){
    // Pour Status : vérifier dans quelle plage se trouve le statut
    $itemAdded = false;
    foreach($columnRanges as $colId => $range){
      // Vérifier si le statut de l'item est dans cette plage
      if($line['idstatus'] == $range['from']){
        // Le statut est exactement le from de cette colonne
        if(isset($jsonColumnList[$colId])){
          $jsonColumnList[$colId]['itemlist'][] = $jsonItemList[$key];
          $itemAdded = true;
          break;
        }
      }else{
        // Vérifier si le statut est entre from et to
        $fromOrder = SqlList::getFieldFromId('Status', $range['from'], 'sortOrder');
        $itemOrder = SqlList::getFieldFromId('Status', $line['idstatus'], 'sortOrder');
        $idleStatus = SqlList::getFieldFromId('Status', $line['idstatus'], 'idle');
        
        if($range['to'] !== null){
          $toOrder = SqlList::getFieldFromId('Status', $range['to'], 'sortOrder');
          if($itemOrder >= $fromOrder && $itemOrder < $toOrder){
            if(isset($jsonColumnList[$colId])){
              $jsonColumnList[$colId]['itemlist'][] = $jsonItemList[$key];
              $itemAdded = true;
              break;
            }
          }
        }else{
          // Dernière colonne - tout ce qui est >= from
          if($itemOrder >= $fromOrder and !$idleStatus){
            if(isset($jsonColumnList[$colId])){
              $jsonColumnList[$colId]['itemlist'][] = $jsonItemList[$key];
              $itemAdded = true;
              break;
            }
          }
        }
      }
    }
    
    // Si l'item n'a pas été ajouté et qu'on affiche le backlog
    if(!$itemAdded && ($refreshBacklog or $onlyRefreshBacklog)){
      if(in_array($line['idstatus'], $backlogColumnList) && isset($jsonColumnList[$idBacklogColumn])){
        $jsonColumnList[$idBacklogColumn]['itemlist'][] = $jsonItemList[$key];
      }
    }
  }else{
    // Pour les autres types : vérifier si la valeur est dans les colonnes actives
    if($line['columnvalue'] and isset($jsonColumnList[$line['columnvalue']])){
      $jsonColumnList[$line['columnvalue']]['itemlist'][] = $jsonItemList[$key];
    }else if($refreshBacklog or $onlyRefreshBacklog){
      // Si la valeur est NULL ou 0, l'ajouter au backlog
      if(isset($jsonColumnList[$idBacklogColumn])){
        $jsonColumnList[$idBacklogColumn]['itemlist'][] = $jsonItemList[$key];
      }
    }
  }
}

// ============================================================================
// JSON FORMATTER
// ============================================================================
$nbColumn = 0;
echo '{"identifier":"id",';
echo ' "items":[';
foreach($jsonColumnList as $column){
  echo (++$nbColumn > 1) ? ',' : '';
  echo '{';
  $nbFields = 0;
  foreach($column as $id => $val){
    if($val === null){$val = " ";}
    if($val == ""){$val = " ";}
    echo (++$nbFields > 1) ? ',' : '';
    if(pq_strpos($id, 'name')){
      $val = htmlEncode(htmlEncodeJson($val));
    }else if(is_array($val)){
      $val = json_encode($val);
    }else{
      $val = htmlEncodeJson($val);
    }
    if($id == "itemlist"){
      echo '"'.htmlEncode($id).'": '.$val;
    }else{
      echo '"'.htmlEncode($id).'":"'.$val.'"';
    }
  }
  echo '}';
}
echo ' ] }';
?>
