<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/** ===========================================================================
 * Get the list of projects for dashboard, in Json format
 */

require_once "../tool/projeqtor.php";
session_write_close();
scriptLog('   ->/tool/jsonProjectDashboard.php');


$project     = new Project();
$ppe         = new ProjectPlanningElement();
$status      = new Status();
$risk        = new Risk();
$att         = new Attachment();
$mpe         = new MilestonePlanningElement();
$milestone   = new Milestone();
$affectable  = new Affectable();
$ape         = new ActivityPlanningElement();
$ticket      = new Ticket();
$requirement = new Requirement();
$userStory   = new UserStory();
$bill        = new Bill();

$tblProject     = $project->getDatabaseTableName();             // project
$tblPpe         = $ppe->getDatabaseTableName();                 // planningelement
$tblStatus      = $status->getDatabaseTableName();              // status
$tblRisk        = $risk->getDatabaseTableName();                // risk
$tblAtt         = $att->getDatabaseTableName();                 // attachment
$tblMpe         = $mpe->getDatabaseTableName();                 // milestoneplanning
$tblMilestone   = $milestone->getDatabaseTableName();           // milestone
$tbAffectable   = $affectable->getDatabaseTableName();          // affectable
$tblApe         = $ape->getDatabaseTableName();                 // activityplanningelement
$tblTicket      = $ticket->getDatabaseTableName();              // ticket
$tblRequirement = $requirement->getDatabaseTableName();         // requirement
$tblUserStory   = $userStory->getDatabaseTableName();           // userstory
$tblBill        = $bill->getDatabaseTableName();                // bill


$riskAggSql =
"(SELECT
    idProject AS idproject,
    SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS riskdone,
    SUM(CASE WHEN idle = 1 AND done <> 1 THEN 1 ELSE 0 END) AS riskclosed,
    SUM(CASE WHEN idle <> 1 AND done <> 1 THEN 1 ELSE 0 END) AS risktodo,
    COUNT(*) AS risktotal
  FROM $tblRisk
  GROUP BY idProject
) r";

$technicalProgressSql =
"(WITH RECURSIVE project_tree AS (
  SELECT id, id as root_id
  FROM $tblProject
  UNION ALL
  SELECT p.id, pt.root_id
  FROM $tblProject p
  INNER JOIN project_tree pt ON p.idProject = pt.id
)
SELECT
    pt.root_id AS idproject,
    SUM(COALESCE(ape.unitToRealise, 0)) AS unittorealise,
    SUM(COALESCE(ape.unitRealised, 0)) AS unitrealised,
    SUM(COALESCE(ape.unitLeft, 0)) AS unitleft
  FROM $tblApe ape
  INNER JOIN project_tree pt ON ape.idProject = pt.id
  WHERE ape.refType = 'Activity'
  GROUP BY pt.root_id
) tech";

$ticketAggSql =
"(SELECT
    idProject AS idproject,
    SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS ticketdone,
    SUM(CASE WHEN idle = 1 AND done <> 1 THEN 1 ELSE 0 END) AS ticketclosed,
    SUM(CASE WHEN idle <> 1 AND done <> 1 THEN 1 ELSE 0 END) AS tickettodo,
    COUNT(*) AS tickettotal
  FROM $tblTicket
  GROUP BY idProject
) t";

$requirementAggSql =
"(SELECT
    idProject AS idproject,
    SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS requirementdone,
    SUM(CASE WHEN idle = 1 AND done <> 1 THEN 1 ELSE 0 END) AS requirementclosed,
    SUM(CASE WHEN idle <> 1 AND done <> 1 THEN 1 ELSE 0 END) AS requirementtodo,
    COUNT(*) AS requirementtotal
  FROM $tblRequirement
  GROUP BY idProject
) req";

$userStoryAggSql =
"(SELECT
    idProject AS idproject,
    SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS userstorydone,
    SUM(CASE WHEN idle = 1 AND done <> 1 THEN 1 ELSE 0 END) AS userstoryclosed,
    SUM(CASE WHEN idle <> 1 AND done <> 1 THEN 1 ELSE 0 END) AS userstorytodo,
    COUNT(*) AS userstorytotal
  FROM $tblUserStory
  GROUP BY idProject
) us";

$billAggSql =
"(SELECT
    idProject AS idproject,
    SUM(CASE WHEN done = 1 THEN COALESCE(fullAmount, 0) ELSE 0 END) AS invoiced,
    SUM(CASE WHEN done = 0 THEN COALESCE(fullAmount, 0) ELSE 0 END) AS tobebilled
  FROM $tblBill
  GROUP BY idProject
) bi";

$whereProject  = "p.codeType != 'ADM' AND p.codeType != 'TMP' ";
$whereProject .= "AND p.id IN " . getVisibleProjectsList();

//TODO filter user project

$query  = "SELECT
    p.id                                AS id,
    p.name                              AS name,
    COALESCE(p.color, '#999999')        AS color,
    p.idOrganization                    AS idorganization,
    p.idClient                          AS idclient,
    p.idHealth                          AS idhealth,
    p.idTrend                           AS idtrend,
    p.idQuality                         AS idquality,
    p.idResource                        AS idresource,
    p.idStatus                          AS idstatus,
    p.idle                              AS idle,
    p.paused                            AS paused,
    p.handled                           AS handled,
    p.creationDate                      AS creationdate,
    
    s.name                              AS statusname,
    s.color                             AS statuscolor,
    
    ppe.validatedStartDate              AS validatedstartdate,
    ppe.plannedStartDate                AS plannedstartdate,
    ppe.realStartDate                   AS realstartdate,
    ppe.validatedEndDate                AS validatedenddate,
    ppe.plannedEndDate                  AS plannedenddate,
    ppe.realEndDate                     AS realenddate,
    ppe.validatedWork                   AS validatedwork,
    ppe.realWork                        AS realwork,
    ppe.plannedWork                     AS plannedwork,
    ppe.leftWork                        AS leftwork,
    ppe.totalValidatedCost              AS totalvalidatedcost,
    ppe.totalRealCost                   AS totalrealcost,
    ppe.totalPlannedCost                AS totalplannedcost,
    ppe.totalLeftCost                   AS totalleftcost,
    ppe.wbsSortable                     AS wbs,
    ppe.priority                        AS priority,
    ppe.assignedWork                    AS assignedwork,
    ppe.leftWork                        AS leftwork,
    ppe.inheritedEndDate                AS inheritedenddate,
    ppe.surbooked                       AS surbooked,
    ppe.revenue                         AS revenue,
    ppe.unitProgress                    AS unitprogress,
    
    r.riskclosed                        AS risk_closed,
    r.riskdone                          AS risk_done,
    r.risktodo                          AS risk_todo,
    r.risktotal                         AS risk_total,
    
    tech.unittorealise                  AS tech_unittorealise,
    tech.unitrealised                   AS tech_unitrealised,
    tech.unitleft                       AS tech_unitleft,
    
    t.ticketclosed                      AS ticket_closed,
    t.ticketdone                        AS ticket_done,
    t.tickettodo                        AS ticket_todo,
    t.tickettotal                       AS ticket_total,
    
    req.requirementclosed               AS requirement_closed,
    req.requirementdone                 AS requirement_done,
    req.requirementtodo                 AS requirement_todo,
    req.requirementtotal                AS requirement_total,
    
    us.userstoryclosed                  AS userstory_closed,
    us.userstorydone                    AS userstory_done,
    us.userstorytodo                    AS userstory_todo,
    us.userstorytotal                   AS userstory_total,

    bi.invoiced                         AS bill_invoiced,
    bi.tobebilled                       AS bill_tobebilled,
    
    att.id                              AS idphoto,
    att.fileName                        AS photofilename,
    att2.id                             AS idattachment,
    
    mpe.id                              AS mpeid,
    mpe.plannedEndDate                  AS milestone_plannedenddate,
    mpe.validatedStartDate              AS milestone_validatedstartdate,
    mpe.realStartDate                   AS milestone_realstartdate,
    m.id                                AS milestoneid,
    m.name                              AS milestonename,
    m.idMilestoneType                   AS milestonetypeid,
    mpe.color                           AS milestonecolor,
    m.done                              AS milestonedone,
    
    aff.fullName                        AS resourcename
    
  FROM $tblProject p
  LEFT JOIN $tblStatus s ON s.id = p.idStatus
  LEFT JOIN $tblPpe ppe ON ppe.refType = 'Project' AND ppe.refId = p.id
  LEFT JOIN $riskAggSql ON r.idproject = p.id
  LEFT JOIN $technicalProgressSql ON tech.idproject = p.id
  LEFT JOIN $ticketAggSql ON t.idproject = p.id
  LEFT JOIN $requirementAggSql ON req.idproject = p.id
  LEFT JOIN $userStoryAggSql ON us.idproject = p.id
  LEFT JOIN $billAggSql ON bi.idproject = p.id
  LEFT JOIN $tblAtt att ON att.refType = 'Project' AND att.refId = p.id AND att.isProfilePic = '1'
  LEFT JOIN (SELECT a1.* FROM $tblAtt a1 WHERE a1.refType = 'Project' AND a1.isProfilePic = '0'
      AND a1.id = ( SELECT MAX(a2.id) FROM $tblAtt a2 WHERE a2.refType = 'Project' AND a2.refId = a1.refId AND a2.isProfilePic = '0')) att2 ON att2.refId = p.id
  LEFT JOIN $tblMpe mpe ON mpe.idProject = p.id AND mpe.refType  = 'Milestone'
  LEFT JOIN $tblMilestone m ON m.id = mpe.refId AND m.cancelled != 1
  LEFT JOIN $tbAffectable aff ON aff.id = p.idResource
  
  WHERE $whereProject
  
  ORDER BY p.id, mpe.plannedEndDate ASC, mpe.validatedStartDate ASC";

$result = Sql::query($query);

$jsonProjectList = array();

//$isColorBlind    = (Parameter::getUserParameter('paramColorBlind') == 'true');

$currentProjectId = null;
$projData         = null;
$currentDate = date('Y-m-d');

while ($line = Sql::fetchLine($result)) {
  $projId = $line['id'];
  
  if ($currentProjectId !== null && $projId != $currentProjectId) {
  
    $ppeData = null;
    if ($projData['validatedstartdate'] || $projData['plannedstartdate'] || $projData['realstartdate']) {
      $ppeData = new stdClass();
      $ppeData->validatedStartDate = $projData['validatedstartdate'];
      $ppeData->plannedStartDate   = $projData['plannedstartdate'];
      $ppeData->realStartDate      = $projData['realstartdate'];
      $ppeData->validatedEndDate   = $projData['validatedenddate'];
      $ppeData->plannedEndDate     = $projData['plannedenddate'];
      $ppeData->realEndDate        = $projData['realenddate'];
      $ppeData->validatedWork      = $projData['validatedwork'];
      $ppeData->realWork           = $projData['realwork'];
      $ppeData->plannedWork        = $projData['plannedwork'];
      $ppeData->assignedWork       = $projData['assignedwork'];
      $ppeData->leftWork           = $projData['leftwork'];
      $ppeData->inheritedEndDate   = $projData['inheritedenddate'];
      $ppeData->surbooked          = $projData['surbooked'];
    }
    
    $projData['colorvalidatedstart'] = '';// no color
    if (!$projData['validatedstartdateiso']) {
      $projData['colorplannedstart'] = '#FFFFFF';
    }else if ($projData['plannedstartdateiso'] > $projData['validatedstartdateiso']) {
      $projData['colorplannedstart'] = '#BB5050';
    }else if ($projData['plannedstartdateiso'] <= $projData['validatedstartdateiso']){
      $projData['colorplannedstart'] = (isset($projData['plannedwork']) && $projData['plannedwork']>0) ? '#50BB50' :'#AEC5AE';
    }
    $projData['colorrealstart']= ( !$projData['realstartdateiso'] && $projData['plannedstartdateiso'] < $currentDate) ? '#BB5050': '#50BB50';;
    
    $projData['colorvalidatedrnd'] = '';//no clor
    if (!$projData['validatedenddateiso']) {
      $projData['colorplannedend'] = '#50BB50';
    }else if ($projData['plannedenddateiso'] > $projData['validatedenddateiso']) {
      $projData['colorplannedend'] = '#BB5050';
    }else if ($projData['plannedenddateiso'] <= $projData['validatedenddateiso']){
      $projData['colorplannedend'] = (isset($projData['plannedwork']) && $projData['plannedwork']>0) ? '#50BB50' :'#AEC5AE';
    }
    $projData['colorrealend'] = (!$projData['realenddateiso'] && $projData['plannedenddateiso'] < $currentDate) ? '#BB5050': '#50BB50';
    
    $jsonProjectList[] = $projData;
    $projData = null;
  }
  
  if ($projData === null) {
    $currentProjectId = $projId;
    $projData         = array();
    
    // Project
    $projData['id']             = (int)$line['id'];
    $projData['name']           = $line['name'];
    $projData['color']          = $line['color'];
    $projData['idorganization'] = (int)$line['idorganization'];
    $projData['idclient']       = (int)$line['idclient'];
    $projData['idle']           = (int)$line['idle'];
    $projData['paused']         = (int)$line['paused'];
    $projData['handled']        = (int)$line['handled'];
    
    // Status
    if ($line['idstatus']) {
      $projData['status'] = array(
          'id'    => (int)$line['idstatus'],
          'name'  => $line['statusname'] ?: '',
          'color' => $line['statuscolor'] ?: '#999999'
      );
    } else {
      $projData['status'] = array(
          'id'    => null,
          'name'  => '',
          'color' => '#999999'
      );
    }
    $token = Security::addTokenIndexToUrl();
    // Photo (attachment)
    if ($line['idphoto']) {
      $id = $line['idphoto'];
      $projData['photo']   = "../tool/download.php?class=Attachment&id=$id$token";
      $projData['idphoto'] = (int)$line['idphoto'];
    } else {
      $projData['photo']   = null;
      $projData['idphoto'] = null;
    }
    
    if ($line['idattachment']) {
      $id = $line['idattachment'];
      $projData['lastatt']   = "../tool/download.php?class=Attachment&id=$id$token";
    } else {
      $projData['lastatt']   = null;
    }
    
    // Dates
    $projData['validatedstartdateiso'] = ($line['validatedstartdate'] && $line['validatedstartdate'] != '0000-00-00') ? $line['validatedstartdate'] : null;
    $projData['plannedstartdateiso'] = ($line['plannedstartdate'] && $line['plannedstartdate'] != '0000-00-00') ? $line['plannedstartdate'] : null;
    $projData['realstartdateiso'] = ($line['realstartdate'] && $line['realstartdate'] != '0000-00-00') ? $line['realstartdate'] : null;
    $projData['validatedenddateiso'] = ($line['validatedenddate'] && $line['validatedenddate'] != '0000-00-00') ? $line['validatedenddate'] : null;
    $projData['plannedenddateiso'] = ($line['plannedenddate'] && $line['plannedenddate'] != '0000-00-00') ? $line['plannedenddate'] : null;
    $projData['realenddateiso'] = ($line['realenddate'] && $line['realenddate'] != '0000-00-00') ? $line['realenddate'] : null;
    $projData['creationdateiso'] = ($line['creationdate'] && $line['creationdate'] != '0000-00-00') ? $line['creationdate'] : null;

    $projData['validatedstartdate'] = $projData['validatedstartdateiso'] ? dateFormatter($projData['validatedstartdateiso']) : null;
    $projData['plannedstartdate'] = $projData['plannedstartdateiso'] ? dateFormatter($projData['plannedstartdateiso']) : null;
    $projData['realstartdate'] = $projData['realstartdateiso'] ? dateFormatter($projData['realstartdateiso']) : null;
    $projData['validatedenddate'] = $projData['validatedenddateiso'] ? dateFormatter($projData['validatedenddateiso']) : null;
    $projData['plannedenddate'] = $projData['plannedenddateiso'] ? dateFormatter($projData['plannedenddateiso']) : null;
    $projData['realenddate'] = $projData['realenddateiso'] ? dateFormatter($projData['realenddateiso']) : null;
    $projData['creationdate'] = $projData['creationdateiso'] ? dateFormatter($projData['creationdateiso']) : null;
    
    // Work / Cost
    $projData['validatedwork']       = floatval($line['validatedwork']);
    $projData['realwork']            = floatval($line['realwork']);
    $projData['plannedwork']         = floatval($line['plannedwork']);
    $projData['leftwork']            = floatval($line['leftwork']);
    $projData['totalvalidatedcost']  = floatval($line['totalvalidatedcost']);
    $projData['totalrealcost']       = floatval($line['totalrealcost']);
    $projData['totalplannedcost']    = floatval($line['totalplannedcost']);
    $projData['totalleftcost']       = floatval($line['totalleftcost']);
    $projData['assignedwork']        = floatval($line['assignedwork']);
    $projData['leftwork']            = floatval($line['leftwork']);
    $projData['inheritedenddate']    = $line['inheritedenddate'];
    $projData['surbooked']           = $line['surbooked'];
    
    $projData['wbs']      = $line['wbs'];
    $projData['priority'] = $line['priority'];
    
    // Risk
    $projData['risk'] = array(
        'closed' => (int)($line['risk_closed'] ?: 0),
        'done'   => (int)($line['risk_done']   ?: 0),
        'todo'   => (int)($line['risk_todo']   ?: 0),
        'total'  => (int)($line['risk_total']  ?: 0)
    );
    
    // Financial
    $projData['financial'] = array(
        'revenue' => floatval($line['revenue']),
        'invoiced'    => floatval($line['bill_invoiced'] ?: 0),
        'tobebilled'  => floatval($line['bill_tobebilled'] ?: 0)
    );
    
    // Technical Progress
    $projData['technicalprogress'] = array(
        'unittorealise' => (int)($line['tech_unittorealise'] ?: 0),
        'unitrealised'  => (int)($line['tech_unitrealised']  ?: 0),
        'unitleft'      => (int)($line['tech_unitleft']      ?: 0),
        'unitprogress'  => (int)($line['unitprogress']       ?: 0)
    );
    
    // Tickets
    $projData['ticket'] = array(
        'closed' => (int)($line['ticket_closed'] ?: 0),
        'done'   => (int)($line['ticket_done']   ?: 0),
        'todo'   => (int)($line['ticket_todo']   ?: 0),
        'total'  => (int)($line['ticket_total']  ?: 0)
    );
    
    // Requirements
    $projData['requirement'] = array(
        'closed' => (int)($line['requirement_closed'] ?: 0),
        'done'   => (int)($line['requirement_done']   ?: 0),
        'todo'   => (int)($line['requirement_todo']   ?: 0),
        'total'  => (int)($line['requirement_total']  ?: 0)
    );
    
    // User Stories
    $projData['userstory'] = array(
        'closed' => (int)($line['userstory_closed'] ?: 0),
        'done'   => (int)($line['userstory_done']   ?: 0),
        'todo'   => (int)($line['userstory_todo']   ?: 0),
        'total'  => (int)($line['userstory_total']  ?: 0)
    );
    
    // Manager (idresource + thumb + name)
    $projData['manager'] = array('isfile'=>'', 'file'=>'', 'name'=>'', 'namemanager'=>'', 'id'=>'');
    $responsibleIcon = "";
    $isResponsibleFile=false;
    if ($line['idresource']) {
      $file     = Affectable::getThumbUrl('Affectable', $line['idresource'], 32);
      $userName = pq_htmlspecialchars($line['resourcename']);
      
      if (pq_substr($file,0,6)=='letter') {
        $isResponsibleFile=false;
        $responsibleIcon = pq_strtoupper(pq_mb_substr($userName,0,1,'UTF-8'));
      } else {
        $isResponsibleFile=true;
        $responsibleIcon = $file;
      }
      
      $userNameTitle = $userName.'<br/><span style= font-size:80% ><i>('.ucfirst(i18n('colManager')).')</i></span>';
      
      $projData['manager'] = array(
          'isfile'      => $isResponsibleFile,
          'file'        => htmlEncode($responsibleIcon),
          'name'        => htmlEncode($userNameTitle),
          'namemanager' => htmlEncode($userName),
          'id'          => $line['idresource'],
          'nametitle'   => htmlEncode($userNameTitle)
      );
    }
    
    // Weather
    $projData['weather'] = array(
        'icon'  => SqlList::getFieldFromId("Health", $line['idhealth'], "icon"),
        'name'  => i18n("colIdHealth").' : '.(($line['idhealth'])?SqlList::getNameFromId("Health", $line['idhealth']):i18n('undefinedValue')),
        'color' => SqlList::getFieldFromId("Health", $line['idhealth'], "color")
    );
    
    // Trend
    $projData['trend'] = array(
        'icon'  => SqlList::getFieldFromId("Trend", $line['idtrend'], "icon"),
        'name'  => i18n("colIdTrend").' : '.(($line['idtrend'])?SqlList::getNameFromId("Trend", $line['idtrend']):i18n('undefinedValue')),
        'color' => SqlList::getFieldFromId("Trend", $line['idtrend'], "color")
    );
    
    // Quality
    $projData['quality'] = array(
        'icon'  => SqlList::getFieldFromId("Quality", $line['idquality'],"icon"),
        'name'  => i18n("colIdQuality").' : '.(($line['idquality'])?SqlList::getNameFromId("Quality", $line['idquality']):i18n('undefinedValue')),
        'color' => SqlList::getFieldFromId("Quality", $line['idquality'], "color")
    );
    
    // Milestones
    $projData['milestones']        = array();
    $projData['nextmilestone']     = null;
    $projData['nextmilestonename'] = null;
  }
  
  if ($line['milestoneid']) {
    $hasPlannedEndDate    = ($line['milestone_plannedenddate'] && $line['milestone_plannedenddate'] != '0000-00-00');
    $hasValidatedStartDate = ($line['milestone_validatedstartdate'] && $line['milestone_validatedstartdate'] != '0000-00-00');
    
    if ($hasPlannedEndDate || $hasValidatedStartDate) {
      $isValidated   = $hasValidatedStartDate;
      $milestoneType = $isValidated ? 'validated' : 'planned';
      $milestoneDate = $isValidated
      ? dateFormatter($line['milestone_validatedstartdate'])
      : dateFormatter($line['milestone_plannedenddate']);
      
      $projData['milestones'][] = array(
//          'name'   => htmlEncode($line['milestonename']), PBER #11233
          'name'   => $line['milestonename'],
          'id'     => (int)$line['milestoneid'],
          'date'   => $milestoneDate,
          'validateddate'  => $line['milestone_validatedstartdate'],
          'plannedenddate' => $line['milestone_plannedenddate'],
          'realenddate'    => $line['milestone_realstartdate'],
          'validateddateiso'  => $line['milestone_validatedstartdate'],
          'plannedenddateiso' => $line['milestone_plannedenddate'],
          'realenddateiso'    => $line['milestone_realstartdate'],
          'done'   => $line['milestonedone'],
          'type'   => $milestoneType,
          'idtype' => $line['milestonetypeid'],
          'color'  => $line['milestonecolor'] ?: null
      );
      
      if ($projData['nextmilestone'] === null && !$line['milestonedone']) {
        $projData['nextmilestone']     = $milestoneDate;
        $projData['nextmilestonename'] = $line['milestonename'];
      }
      
    }
  }
}

if ($projData !== null) {
  
  $ppeData = null;
  if ($projData['validatedstartdate'] || $projData['plannedstartdate'] || $projData['realstartdate']) {
    $ppeData = new stdClass();
    $ppeData->validatedStartDate = $projData['validatedstartdate'];
    $ppeData->plannedStartDate   = $projData['plannedstartdate'];
    $ppeData->realStartDate      = $projData['realstartdate'];
    $ppeData->validatedEndDate   = $projData['validatedenddate'];
    $ppeData->plannedEndDate     = $projData['plannedenddate'];
    $ppeData->realEndDate        = $projData['realenddate'];
    $ppeData->validatedWork      = $projData['validatedwork'];
    $ppeData->realWork           = $projData['realwork'];
    $ppeData->plannedWork        = $projData['plannedwork'];
    $ppeData->assignedWork       = $projData['assignedwork'];
    $ppeData->leftWork           = $projData['leftwork'];
    $ppeData->inheritedEndDate   = $projData['inheritedenddate'];
    $ppeData->surbooked          = $projData['surbooked'];
  }
  
  $projData['colorvalidatedstart'] = '';// no color
  if (!$projData['validatedstartdateiso']) {
    $projData['colorplannedstart'] = '#FFFFFF';
  }else if ($projData['plannedstartdateiso'] > $projData['validatedstartdateiso']) {
    $projData['colorplannedstart'] = '#BB5050';
  }else if ($projData['plannedstartdateiso'] <= $projData['validatedstartdateiso']){
    $projData['colorplannedstart'] = (isset($projData['plannedwork']) && $projData['plannedwork']>0) ? '#50BB50' :'#AEC5AE';
  }
  $projData['colorrealstart']= ( !$projData['realstartdateiso'] && $projData['plannedstartdateiso'] < $currentDate) ? '#BB5050': '#50BB50';;
  
  $projData['colorvalidatedrnd'] = '';//no clor
  if (!$projData['validatedenddateiso']) {
    $projData['colorplannedend'] = '#50BB50';
  }else if ($projData['plannedenddateiso'] > $projData['validatedenddateiso']) {
    $projData['colorplannedend'] = '#BB5050';
  }else if ($projData['plannedenddateiso'] <= $projData['validatedenddateiso']){
    $projData['colorplannedend'] = (isset($projData['plannedwork']) && $projData['plannedwork']>0) ? '#50BB50' :'#AEC5AE';
  }
  $projData['colorrealend'] = (!$projData['realenddateiso'] && $projData['plannedenddateiso'] < $currentDate) ? '#BB5050': '#50BB50';
  
  
  $jsonProjectList[] = $projData;
}

// ========== JSON FORMATTER ===========
if (count($jsonProjectList) > 0) {
  echo '{"identifier":"id",';
  echo ' "items":[';
  
  $first = true;
  foreach ($jsonProjectList as $projData) {
    if (!$first) echo ',';
    $first = false;
    
    echo '{';
    $firstField = true;
    foreach ($projData as $key => $value) {
      if (!$firstField) echo ',';
      $firstField = false;
      
      if ($value === null) {
        echo '"' . htmlEncode($key) . '":null';
      } else if (is_bool($value)) {
        echo '"' . htmlEncode($key) . '":' . ($value ? 'true' : 'false');
      } else if ($key === 'wbs' || $key === 'priority') {
        echo '"' . htmlEncode($key) . '":"' . htmlEncodeJson($value) . '"';
      } else if (is_numeric($value)) {
        echo '"' . htmlEncode($key) . '":' . $value;
      } else if (is_array($value)) {
        echo '"' . htmlEncode($key) . '":' . json_encode($value);
      } else {
        echo '"' . htmlEncode($key) . '":"' . htmlEncodeJson($value) . '"';
      }
    }
    echo '}';
  }
  echo ']}';
} else {
  echo i18n('noDataToDisplay');
}
