<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

require_once "../tool/projeqtor.php";
session_write_close();
scriptLog('   ->/tool/jsonProjectDashboardDetail.php');

$idProject = RequestHandler::getId('idProject');

if (!$idProject) {
  echo '{"error":"' . i18n('projectIdRequired') . '"}';
  scriptLog('   ERROR: No project ID provided');
  return;
}

function sqlJsonAgg($jsonExpr, $orderBy = '') {
  if (Sql::isPgsql()) {
    $orderClause = $orderBy ? " ORDER BY $orderBy" : '';
    return "JSON_AGG($jsonExpr$orderClause)";
  } else {
    return "JSON_ARRAYAGG($jsonExpr)";
  }
}

function sqlJsonObject($pairs) {
  $items = array();
  foreach ($pairs as $key => $expr) {
    $items[] = "'$key', $expr";
  }
  if (Sql::isPgsql()) {
    return "JSON_BUILD_OBJECT(" . implode(', ', $items) . ")";
  } else {
    return "JSON_OBJECT(" . implode(', ', $items) . ")";
  }
}

$project = new Project();
$ppe = new ProjectPlanningElement();
$status = new Status();
$att = new Attachment();
$affectable = new Affectable();
$projectType = new ProjectType();
$profil = new Profile();
$affectation = new Affectation();
$baseline = new Baseline();
$milestone = new Milestone();
$mpe = new MilestonePlanningElement();
$milestoneType = new MilestoneType();
$planningMode = new PlanningMode();
$risk = new Risk();
$severity = new Severity();
$likelihood = new Likelihood();
$criticality = new Criticality();
$riskType = new RiskType();
$work = new Work();
$plannedWork = new PlannedWork();
$assignment = new Assignment();
$projectExpense = new ProjectExpense();
$pe = new PlanningElement();
$command = new Command();
$workCommand = new WorkCommand();
$opportunity = new Opportunity();
$opportunityType = new OpportunityType();
$raciModel = new RaciModel();

$tblProject        = $project->getDatabaseTableName();
$tblPpe            = $ppe->getDatabaseTableName();
$tblStatus         = $status->getDatabaseTableName();
$tblAtt            = $att->getDatabaseTableName();
$tbAffectable      = $affectable->getDatabaseTableName();
$tblProjectType    = $projectType->getDatabaseTableName();
$tblProfile        = $profil->getDatabaseTableName();
$tblAffectation    = $affectation->getDatabaseTableName();
$tblBaseline       = $baseline->getDatabaseTableName();
$tblMpe            = $mpe->getDatabaseTableName();
$tblMilestone      = $milestone->getDatabaseTableName();
$tblMilestoneType  = $milestoneType->getDatabaseTableName();
$tblPlanningMode   = $planningMode->getDatabaseTableName();
$tblRisk           = $risk->getDatabaseTableName();
$tblSeverity       = $severity->getDatabaseTableName();
$tblLikelihood     = $likelihood->getDatabaseTableName();
$tblCriticality    = $criticality->getDatabaseTableName();
$tblRiskType       = $riskType->getDatabaseTableName();
$tblWork           = $work->getDatabaseTableName();
$tblPlannedWork    = $plannedWork->getDatabaseTableName();
$tblAssignment     = $assignment->getDatabaseTableName();
$tblProjectExpense = $projectExpense->getDatabaseTableName();
$tblPe             = $pe->getDatabaseTableName();
$tblCommand        = $command->getDatabaseTableName();
$tblWorkCommand    = $workCommand->getDatabaseTableName();
$tblOpportunity     = $opportunity->getDatabaseTableName();
$tblOpportunityType = $opportunityType->getDatabaseTableName();

// Agrégats JSON
$resJsonObj = sqlJsonObject([
  'idaffectation' => 'aff_res.id',
  'id'            => 'aff_res.idResource',
  'name'          => 'COALESCE(res.fullName, \'\')',
  'idprofile'     => 'COALESCE(aff_res.idProfile, NULL)',
  'nameprofile'   => 'COALESCE(prf_res.name, \'\')',
]);
$resAgg = sqlJsonAgg($resJsonObj, 'res.fullName');

$msJsonObj = sqlJsonObject([
  'id'               => 'm.id',
  'name'             => 'm.name',
  'idtype'           => 'COALESCE(m.idMilestoneType, NULL)',
  'mode'             => 'COALESCE(mm.name, \'\')',
  'idstatus'         => 'COALESCE(m.idStatus, NULL)',
  'status'           => 'COALESCE(ms.name, \'\')',
  'colorstatus'      => 'COALESCE(ms.color, \'\')',
  'type'             => 'COALESCE(mt.name, \'\')',
  'plannedenddate'   => 'COALESCE(mpe.plannedEndDate, NULL)',
  'validateddate'    => 'COALESCE(mpe.validatedStartDate, NULL)',
  'realenddate'      => 'COALESCE(mpe.realStartDate, NULL)',
  'initialstartdate' => 'COALESCE(mpe.initialStartDate, NULL)',
]);
$msAgg = sqlJsonAgg($msJsonObj, 'mpe.plannedEndDate');

$riskJsonObj = sqlJsonObject([
  'id'                   => 'risk.id',
  'name'                 => 'risk.name',
  'idseverity'           => 'COALESCE(risk.idSeverity, NULL)',
  'severityname'         => 'COALESCE(sev.name, \'\')',
  'severitycolor'        => 'COALESCE(sev.color, \'#999999\')',
  'idlikelihood'         => 'COALESCE(risk.idLikelihood, NULL)',
  'likelihoodname'       => 'COALESCE(lik.name, \'\')',
  'likelihoodcolor'      => 'COALESCE(lik.color, \'#999999\')',
  'idcriticality'        => 'COALESCE(risk.idCriticality, NULL)',
  'criticalityname'      => 'COALESCE(cri.name, \'\')',
  'criticalitycolor'     => 'COALESCE(cri.color, \'#999999\')',
  'idrisktype'           => 'COALESCE(risk.idRiskType, NULL)',
  'risktype'             => 'COALESCE(rt.name, \'\')',
  'impactcost'           => 'COALESCE(risk.impactCost, 0)',
  'projectreserveamount' => 'COALESCE(risk.projectReserveAmount, 0)',
  'status'               => 'COALESCE(mr.name, \'\')',
  'colorstatus'          => 'COALESCE(mr.color, \'#999999\')',
]);
$riskAgg = sqlJsonAgg($riskJsonObj, 'risk.name');

$wcJsonObj = sqlJsonObject([
  'id' => 'COALESCE(wc.id, 0)',
  'name' => 'COALESCE(wc.name, \'\')',
  'idworkunit' => 'COALESCE(wc.idWorkUnit, 0)',
  'idcomplexity' => 'COALESCE(wc.idComplexity, 0)',
  'commandquantity' => 'COALESCE(wc.commandQuantity, 0)',
  'commandamount' => 'COALESCE(wc.commandAmount, 0)',
  'commandamountlocal' => 'COALESCE(wc.commandAmountLocal, 0)',
  'donequantity' => 'COALESCE(wc.doneQuantity, 0)',
  'doneamount' => 'COALESCE(wc.doneAmount, 0)',
  'doneamountlocal' => 'COALESCE(wc.doneAmountLocal, 0)',
  'acceptedquantity' => 'COALESCE(wc.acceptedQuantity, 0)',
  'acceptedamount' => 'COALESCE(wc.acceptedAmount, 0)',
  'acceptedamountlocal' => 'COALESCE(wc.acceptedAmountLocal, 0)',
  'billedquantity' => 'COALESCE(wc.billedQuantity, 0)',
  'billedamount' => 'COALESCE(wc.billedAmount, 0)',
  'billedamountlocal' => 'COALESCE(wc.billedAmountLocal, 0)',
]);
$wcAgg = sqlJsonAgg($wcJsonObj, 'wc.name');

$oppJsonObj = sqlJsonObject([
  'id' => 'opp.id',
  'name' => 'opp.name',
  'idseverity' => 'COALESCE(opp.idSeverity, NULL)',
  'severityname' => 'COALESCE(sev_o.name, \'\')',
  'severitycolor' => 'COALESCE(sev_o.color, \'#999999\')',
  'idlikelihood' => 'COALESCE(opp.idLikelihood, NULL)',
  'likelihoodname' => 'COALESCE(lik_o.name, \'\')',
  'likelihoodcolor' => 'COALESCE(lik_o.color, \'#999999\')',
  'idcriticality' => 'COALESCE(opp.idCriticality, NULL)',
  'criticalityname' => 'COALESCE(cri_o.name, \'\')',
  'criticalitycolor' => 'COALESCE(cri_o.color, \'#999999\')',
  'idopportunitytype' => 'COALESCE(opp.idOpportunityType, NULL)',
  'opportunitytype' => 'COALESCE(ot.name, \'\')',
  'impactcost' => 'COALESCE(opp.impactCost, 0)',
  'projectreserveamount' => 'COALESCE(opp.projectReserveAmount, 0)',
  'status' => 'COALESCE(mo.name, \'\')',
  'colorstatus' => 'COALESCE(mo.color, \'#999999\')',
]);
$oppAgg = sqlJsonAgg($oppJsonObj, 'opp.name');

$attJsonObj = sqlJsonObject([
    'id' => 'att_list.id',
    'filename' => 'COALESCE(att_list.fileName, \'\')',
    'link' => 'COALESCE(att_list.link, \'\')',
    'mimetype' => 'COALESCE(att_list.mimeType, \'\')',
    'subdirectory'=> 'COALESCE(att_list.subDirectory, \'\')',
]);
$attAgg = sqlJsonAgg($attJsonObj, 'att_list.id');

$resSub = "
  SELECT COALESCE($resAgg, '[]') AS all_resources
  FROM $tblAffectation aff_res
  LEFT JOIN $tbAffectable res ON res.id = aff_res.idResource
  LEFT JOIN $tblProfile prf_res ON prf_res.id = aff_res.idProfile
  WHERE aff_res.idProject = p.id
";

$msSub = "
  SELECT COALESCE($msAgg, '[]') AS all_milestones
  FROM $tblMpe mpe
  JOIN $tblMilestone m ON m.id = mpe.refId AND m.cancelled != 1
  LEFT JOIN $tblStatus ms ON ms.id = m.idStatus
  LEFT JOIN $tblMilestoneType mt ON mt.id = m.idMilestoneType
  LEFT JOIN $tblPlanningMode mm ON mm.id = mpe.idPlanningMode
  WHERE mpe.idProject = p.id AND mpe.refType = 'Milestone'
";

$riskSub = "
  SELECT COALESCE($riskAgg, '[]') AS all_risks
  FROM $tblRisk risk
  LEFT JOIN $tblSeverity sev ON sev.id = risk.idSeverity
  LEFT JOIN $tblLikelihood lik ON lik.id = risk.idLikelihood
  LEFT JOIN $tblCriticality cri ON cri.id = risk.idCriticality
  LEFT JOIN $tblRiskType rt  ON rt.id = risk.idRiskType
  LEFT JOIN $tblStatus mr  ON mr.id = risk.idStatus
  WHERE risk.idProject = p.id AND risk.cancelled != 1
";

$oppSub = "
  SELECT COALESCE($oppAgg, '[]') AS all_opportunities
  FROM $tblOpportunity opp
  LEFT JOIN $tblSeverity sev_o ON sev_o.id = opp.idSeverity
  LEFT JOIN $tblLikelihood lik_o ON lik_o.id = opp.idLikelihood
  LEFT JOIN $tblCriticality cri_o ON cri_o.id = opp.idCriticality
  LEFT JOIN $tblOpportunityType ot ON ot.id = opp.idOpportunityType
  LEFT JOIN $tblStatus mo ON mo.id = opp.idStatus
  WHERE opp.idProject = p.id AND opp.cancelled != 1
";

$attSub = "
  SELECT COALESCE($attAgg, '[]') AS all_attachments
  FROM $tblAtt att_list
  WHERE att_list.refType = 'Project'
    AND att_list.refId = p.id
    AND att_list.isProfilePic = '0'
";


$query = "SELECT
    p.id                                AS id,
    p.name                              AS name,
    p.description                       AS description,
    p.objectives                        AS objectives,
    COALESCE(p.color, '#999999')        AS color,
    p.idProjectType                     AS idprojecttype,
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
    p.strategicValue                    AS strategicvalue,
    p.benefitValue                      AS benefitvalue,
    p.idRaciModel                       AS idracimodel,
    
    pt.name                             AS projecttypename,
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
    ppe.totalAssignedCost               AS totalassignedcost,
    ppe.wbsSortable                     AS wbs,
    ppe.priority                        AS priority,
    ppe.assignedWork                    AS assignedwork,
    ppe.revenue                         AS revenue,
    ppe.expenseValidatedAmount          AS expensevalidatedamount,
    ppe.expenseAssignedAmount           AS expenseassignedamount,
    ppe.expenseRealAmount               AS expenserealamount,
    ppe.expenseLeftAmount               AS expenseleftamount,
    ppe.expensePlannedAmount            AS expenseplannedamount,
    
    (SELECT COALESCE(SUM(w.cost), 0)
     FROM $tblWork w
     WHERE w.idProject = p.id)                           AS realresourcecost,
     
    (SELECT COALESCE(SUM(pw.work * a.newDailyCost), 0)
     FROM $tblPlannedWork pw
     JOIN $tblAssignment a ON a.id = pw.idAssignment
     WHERE pw.idProject = p.id)                          AS plannedresourcecost,
     
    (SELECT COALESCE(SUM(exp.realAmount), 0)
     FROM $tblProjectExpense exp
     WHERE exp.idProject = p.id
       AND exp.expenseRealDate IS NOT NULL
       AND exp.cancelled = 0)                            AS realprojectexpense,
       
    (SELECT COALESCE(SUM(exp.plannedAmount), 0)
     FROM $tblProjectExpense exp
     WHERE exp.idProject = p.id
       AND exp.expenseRealDate IS NULL
       AND exp.cancelled = 0)                            AS plannedprojectexpense,
       
    (SELECT COALESCE(SUM(pe.realCost), 0)
     FROM $tblPe pe
     WHERE pe.idProject = p.id
       AND pe.elementary = 1
       AND pe.cancelled = 0)                             AS realactivitycost,
       
    (SELECT COALESCE(SUM(pe.plannedCost), 0)
     FROM $tblPe pe
     WHERE pe.idProject = p.id
       AND pe.elementary = 1
       AND pe.cancelled = 0)                             AS plannedactivitycost,
       
    (SELECT COALESCE(SUM(pe.validatedCost), 0)
     FROM $tblPe pe
     WHERE pe.idProject = p.id
       AND pe.elementary = 1
       AND pe.cancelled = 0)                             AS validatedactivitycost,
       
    att.id                              AS idphoto,
    att.fileName                        AS photofilename,
    aff.fullName                        AS resourcename,
    ba.id                               AS idbaseline,
    
    ($resSub)                           AS all_resources,
    ($msSub)                            AS all_milestones,
    ($riskSub)                          AS all_risks,
    ($oppSub)                           AS all_opportunities,
    ($attSub)                           AS all_attachments
    
FROM $tblProject p
LEFT JOIN $tblProjectType pt ON pt.id        = p.idProjectType
LEFT JOIN $tblStatus s       ON s.id         = p.idStatus
LEFT JOIN $tblPpe ppe        ON ppe.refType  = 'Project' AND ppe.refId = p.id
LEFT JOIN $tblAtt att        ON att.refType  = 'Project' AND att.refId = p.id AND att.isProfilePic = '1'
LEFT JOIN $tbAffectable aff  ON aff.id       = p.idResource
LEFT JOIN $tblBaseline ba    ON ba.idProject = p.id

WHERE p.id = " . Sql::str($idProject);
    
    $result = Sql::query($query);
    $line   = Sql::fetchLine($result);
    
    $queryCommands = "SELECT
    cm.id                               AS id,
    cm.name                             AS name,
    cm.reference                        AS reference,
    cm.fullAmount                       AS fullamount,
    cm.fullAmountLocal                  AS fullamountlocal,
    cm.untaxedAmount                    AS untaxedamount,
    cm.untaxedAmountLocal               AS untaxedamountlocal,
    cm.idStatus                         AS idstatus,
    s.name                              AS statusname,
    s.color                             AS statuscolor,
    COALESCE(wcg.workcommands, '[]')    AS all_workcommands
FROM $tblCommand cm
LEFT JOIN $tblStatus s ON s.id = cm.idStatus
LEFT JOIN (
    SELECT
        wc.idCommand                    AS idcommand,
        $wcAgg                          AS workcommands
    FROM $tblWorkCommand wc
    WHERE wc.idCommand IS NOT NULL
    GROUP BY wc.idCommand
) wcg ON wcg.idCommand = cm.id
WHERE cm.idProject = " . Sql::str($idProject) . "
ORDER BY cm.name";
    
$resultCommands=Sql::query($queryCommands);

$currentDate=date('Y-m-d');
$token=Security::addTokenIndexToUrl();

if ($line) {
  $projData=array();

  $projData['id']=(int)$line['id'];
  $projData['name']=$line['name'];
  $projData['description']=$line['description']?html_entity_decode($line['description'], ENT_QUOTES, 'UTF-8'):'';
  $projData['objectives']=$line['objectives']?html_entity_decode($line['objectives'], ENT_QUOTES, 'UTF-8'):'';
  $projData['color']=$line['color'];
  $projData['idorganization']=(int)$line['idorganization'];
  $projData['idclient']=(int)$line['idclient'];
  $projData['idle']=(int)$line['idle'];
  $projData['paused']=(int)$line['paused'];
  $projData['handled']=(int)$line['handled'];
  $projData['strategicvalue']=$line['strategicvalue'];
  $projData['benefitvalue']=$line['benefitvalue'];

  // Project type
  $projData['projecttype']=array('id'=>(int)$line['idprojecttype'], 'name'=>$line['projecttypename']?:'');

  // Status
  if ($line['idstatus']) {
    $projData['status']=array(
        'id'=>(int)$line['idstatus'],
        'name'=>$line['statusname']?:'',
        'color'=>$line['statuscolor']?:'#999999');
  } else {
    $projData['status']=array('id'=>null, 'name'=>'', 'color'=>'#999999');
  }
 
  // Photo
  if ($line['idphoto']) {
    $id=$line['idphoto'];
    $projData['photo']="../tool/download.php?class=Attachment&id=$id$token";
    $projData['idphoto']=(int)$line['idphoto'];
  } else {
    $projData['photo']=null;
    $projData['idphoto']=null;
  }
  
  // Dates
  $projData['validatedstartdateiso']=($line['validatedstartdate']&&$line['validatedstartdate']!='0000-00-00')?$line['validatedstartdate']:null;
  $projData['plannedstartdateiso']=($line['plannedstartdate']&&$line['plannedstartdate']!='0000-00-00')?$line['plannedstartdate']:null;
  $projData['realstartdateiso']=($line['realstartdate']&&$line['realstartdate']!='0000-00-00')?$line['realstartdate']:null;
  $projData['validatedenddateiso']=($line['validatedenddate']&&$line['validatedenddate']!='0000-00-00')?$line['validatedenddate']:null;
  $projData['plannedenddateiso']=($line['plannedenddate']&&$line['plannedenddate']!='0000-00-00')?$line['plannedenddate']:null;
  $projData['realenddateiso']=($line['realenddate']&&$line['realenddate']!='0000-00-00')?$line['realenddate']:null;

  $projData['validatedstartdate']=$projData['validatedstartdateiso']?dateFormatter($projData['validatedstartdateiso']):null;
  $projData['plannedstartdate']=$projData['plannedstartdateiso']?dateFormatter($projData['plannedstartdateiso']):null;
  $projData['realstartdate']=$projData['realstartdateiso']?dateFormatter($projData['realstartdateiso']):null;
  $projData['validatedenddate']=$projData['validatedenddateiso']?dateFormatter($projData['validatedenddateiso']):null;
  $projData['plannedenddate']=$projData['plannedenddateiso']?dateFormatter($projData['plannedenddateiso']):null;
  $projData['realenddate']=$projData['realenddateiso']?dateFormatter($projData['realenddateiso']):null;

  // Work / Cost
  $projData['validatedwork']=floatval($line['validatedwork']);
  $projData['realwork']=floatval($line['realwork']);
  $projData['plannedwork']=floatval($line['plannedwork']);
  $projData['leftwork']=floatval($line['leftwork']);
  $projData['assignedwork']=floatval($line['assignedwork']);
  $projData['totalvalidatedcost']=floatval($line['totalvalidatedcost']);
  $projData['totalrealcost']=floatval($line['totalrealcost']);
  $projData['totalplannedcost']=floatval($line['totalplannedcost']);
  $projData['totalleftcost']=floatval($line['totalleftcost']);
  $projData['totalassignedcost']=floatval($line['totalassignedcost']);
  $projData['revenue']=(int)$line['revenue'];
  $projData['expensevalidatedamount']=floatval($line['expensevalidatedamount']);
  $projData['expenseassignedamount']=floatval($line['expenseassignedamount']);
  $projData['expenserealamount']=floatval($line['expenserealamount']);
  $projData['expenseleftamount']=floatval($line['expenseleftamount']);
  $projData['expenseplannedamount']=floatval($line['expenseplannedamount']);
  $projData['realresourcecost']=floatval($line['realresourcecost']);
  $projData['plannedresourcecost']=floatval($line['plannedresourcecost']);
  $projData['realprojectexpense']=floatval($line['realprojectexpense']);
  $projData['plannedprojectexpense']=floatval($line['plannedprojectexpense']);
  $projData['realactivitycost']=floatval($line['realactivitycost']);
  $projData['plannedactivitycost']=floatval($line['plannedactivitycost']);
  $projData['validatedactivitycost']=floatval($line['validatedactivitycost']);

  $projData['wbs']=$line['wbs'];
  $projData['priority']=$line['priority'];

  // Color dates
  $projData['colorvalidatedstart']='';
  if (!$projData['validatedstartdateiso']) {
    $projData['colorplannedstart']='#FFFFFF';
  } else if ($projData['plannedstartdateiso']>$projData['validatedstartdateiso']) {
    $projData['colorplannedstart']='#BB5050';
  } else {
    $projData['colorplannedstart']=($projData['plannedwork']>0)?'#50BB50':'#AEC5AE';
  }
  $projData['colorrealstart']=(!$projData['realstartdateiso']&&$projData['plannedstartdateiso']<$currentDate)?'#BB5050':'#50BB50';

  $projData['colorvalidatedrnd']='';
  if (!$projData['validatedenddateiso']) {
    $projData['colorplannedend']='#50BB50';
  } else if ($projData['plannedenddateiso']>$projData['validatedenddateiso']) {
    $projData['colorplannedend']='#BB5050';
  } else {
    $projData['colorplannedend']=($projData['plannedwork']>0)?'#50BB50':'#AEC5AE';
  }
  $projData['colorrealend']=(!$projData['realenddateiso']&&$projData['plannedenddateiso']<$currentDate)?'#BB5050':'#50BB50';

  // Manager
  $projData['manager']=array('isfile'=>'', 'file'=>'', 'name'=>'', 'namemanager'=>'', 'id'=>'');
  if ($line['idresource']) {
    $file=Affectable::getThumbUrl('Affectable', $line['idresource'], 32);
    $userName=pq_htmlspecialchars($line['resourcename']);
    if (pq_substr($file, 0, 6)=='letter') {
      $isResponsibleFile=false;
      $responsibleIcon=pq_strtoupper(pq_mb_substr($userName, 0, 1, 'UTF-8'));
    } else {
      $isResponsibleFile=true;
      $responsibleIcon=$file;
    }
    $userNameTitle=$userName . '<br/><span style= font-size:80% ><i>(' . i18n('colResponsible') . ')</i></span>';
    $projData['manager']=array(
        'isfile'=>$isResponsibleFile,
        'file'=>htmlEncode($responsibleIcon),
        'name'=>htmlEncode($userNameTitle),
        'namemanager'=>htmlEncode($userName),
        'id'=>$line['idresource'],
        'nametitle'=>htmlEncode($userNameTitle));
  }

  // Weather / Trend / Quality
  $projData['weather']=array(
      'icon'=>SqlList::getFieldFromId("Health", $line['idhealth'], "icon"),
      'name'=>i18n("colIdHealth") . ' : ' . ($line['idhealth']?SqlList::getNameFromId("Health", $line['idhealth']):i18n('undefinedValue')),
      'color'=>SqlList::getFieldFromId("Health", $line['idhealth'], "color"));
  $projData['trend']=array(
      'icon'=>SqlList::getFieldFromId("Trend", $line['idtrend'], "icon"),
      'name'=>i18n("colIdTrend") . ' : ' . ($line['idtrend']?SqlList::getNameFromId("Trend", $line['idtrend']):i18n('undefinedValue')),
      'color'=>SqlList::getFieldFromId("Trend", $line['idtrend'], "color"));
  $projData['quality']=array(
      'icon'=>SqlList::getFieldFromId("Quality", $line['idquality'], "icon"),
      'name'=>i18n("colIdQuality") . ' : ' . ($line['idquality']?SqlList::getNameFromId("Quality", $line['idquality']):i18n('undefinedValue')),
      'color'=>SqlList::getFieldFromId("Quality", $line['idquality'], "color"));

  $projData['idbaseline']=(int)$line['idbaseline'];

  // Ressources
  $resources=array();
  $rawResources=json_decode($line['all_resources']??'[]', true);
  if (is_array($rawResources)) {
    foreach ($rawResources as $res) {
      if (!empty($res['id'])) {
        $thumbFile=Affectable::getThumbUrl('Affectable', $res['id'], 32);
        if (pq_substr($thumbFile, 0, 6)=='letter') {
          $res['isfile']=false;
          $res['file']=pq_strtoupper(pq_mb_substr($res['name'], 0, 1, 'UTF-8'));
        } else {
          $res['isfile']=true;
          $res['file']=htmlEncode($thumbFile);
        }
        $resources[]=$res;
      }
    }
  }
  $projData['resources']=$resources;

  // Milestones
  $milestones=array();
  $rawMilestones=json_decode($line['all_milestones']??'[]', true);
  if (is_array($rawMilestones)) {
    foreach ($rawMilestones as $ms) {
      if (!empty($ms['id'])) {
        $ms['plannedenddateiso']=($ms['plannedenddate']&&$ms['plannedenddate']!='0000-00-00')?$ms['plannedenddate']:null;
        $ms['validateddateiso']=($ms['validateddate']&&$ms['validateddate']!='0000-00-00')?$ms['validateddate']:null;
        $ms['realenddateiso']=($ms['realenddate']&&$ms['realenddate']!='0000-00-00')?$ms['realenddate']:null;
        $ms['plannedenddate']=($ms['plannedenddate']&&$ms['plannedenddate']!='0000-00-00')?dateFormatter($ms['plannedenddate']):null;
        $ms['validateddate']=($ms['validateddate']&&$ms['validateddate']!='0000-00-00')?dateFormatter($ms['validateddate']):null;
        $ms['realenddate']=($ms['realenddate']&&$ms['realenddate']!='0000-00-00')?dateFormatter($ms['realenddate']):null;
        $ms['initialstartdate']=($ms['initialstartdate']&&$ms['initialstartdate']!='0000-00-00')?dateFormatter($ms['initialstartdate']):null;
        $milestones[]=$ms;
      }
    }
  }
  $projData['milestones']=$milestones;

  // Risks
  $risks=array();
  $rawRisks=json_decode($line['all_risks']??'[]', true);
  if (is_array($rawRisks)) {
    foreach ($rawRisks as $risk) {
      if (!empty($risk['id'])) {
        $risks[]=$risk;
      }
    }
  }
  $projData['risks']=$risks;

  // Commandes
  $commands=array();
  while ($commandLine=Sql::fetchLine($resultCommands)) {
    $workCommands=array();
    $rawWc=json_decode($commandLine['all_workcommands'], true);
    if (is_array($rawWc)) {
      foreach ($rawWc as $wc) {
        $wc['nameworkunit']=SqlList::getNameFromId('WorkUnit', (int)$wc['idworkunit']);
        $wc['namecomplexity']=SqlList::getNameFromId('Complexity', (int)$wc['idcomplexity']);
        $workCommands[]=$wc;
      }
    }
    $commands[]=array(
        'id'=>(int)$commandLine['id'],
        'name'=>$commandLine['name'],
        'reference'=>$commandLine['reference'],
        'fullAmount'=>floatval($commandLine['fullamount']),
        'fullAmountLocal'=>floatval($commandLine['fullamountlocal']),
        'untaxedAmount'=>floatval($commandLine['untaxedamount']),
        'untaxedAmountLocal'=>floatval($commandLine['untaxedamountlocal']),
        'idstatus'=>(int)$commandLine['idstatus'],
        'statusname'=>$commandLine['statusname'],
        'statuscolor'=>$commandLine['statuscolor'],
        'workcommands'=>$workCommands);
  }
  $projData['commands']=$commands;
  
  // Opportunities
  $opportunities = array();
  $rawOpps = json_decode($line['all_opportunities'] ?? '[]', true);
  if (is_array($rawOpps)) {
    foreach ($rawOpps as $opp) {
      if (!empty($opp['id'])) {
        $opportunities[] = $opp;
      }
    }
  }
  $projData['opportunities'] = $opportunities;
  
  // Attachements
  $attachments = array();
  $rawAtts = json_decode($line['all_attachments'] ?? '[]', true);
  if (is_array($rawAtts)) {
    foreach ($rawAtts as $attData) {
      if (!empty($attData['id'])) {
        $attObj = new Attachment($attData['id']);
        if (!empty($attData['link'])) {
          $attData['downloadurl'] = $attData['link'];
          $attData['islink']      = true;
          $attData['thumburl']    = '../view/img/mime/html.png';
        } else {
          $token = Security::addTokenIndexToUrl();
          $attData['downloadurl'] = "../tool/download.php?class=Attachment&id=" . intval($attData['id']) . $token;
          $attData['islink']      = false;         
          if ($attObj->isThumbable()) {
            $attData['thumburl'] = getImageThumb($attObj->getFullPathFileName(), 32);
          } else {
            $fileName = $attData['filename'];
            $ext      = strtolower(pathinfo($fileName, PATHINFO_EXTENSION));
            $attData['thumburl'] = '../view/img/mime/' . ($ext ?: 'bin') . '.png';
          }
        }
        
        $attachments[] = $attData;
      }
    }
  }
  $projData['attachments'] = $attachments;

  // RACI
  $raciHtml = '';
  if (!empty($line['idracimodel'])) {
    $raciModelObj = new RaciModel((int)$line['idracimodel']);
    if ($raciModelObj->id) {
      $raciHtml = $raciModelObj->drawMatrixDashboard((int)$line['id']);
    }
  }
  $projData['racihtml'] = $raciHtml;

  
  // Formatage JSON
  echo '{';
  $firstField=true;
  foreach ($projData as $key=>$value) {
    if (!$firstField) echo ',';
    $firstField=false;
    if ($value===null) {
      echo '"' . htmlEncode($key) . '":null';
    } else if (is_bool($value)) {
      echo '"' . htmlEncode($key) . '":' . ($value?'true':'false');
    } else if (is_numeric($value)&&!in_array($key, array('wbs', 'priority'))) {
      echo '"' . htmlEncode($key) . '":' . $value;
    } else if (is_array($value)) {
      echo '"' . htmlEncode($key) . '":' . json_encode($value, JSON_HEX_TAG|JSON_HEX_APOS|JSON_HEX_AMP);
    } else if (in_array($key, array('description', 'objectives', 'racihtml'))) {
      echo '"' . htmlEncode($key) . '":' . json_encode($value, JSON_HEX_TAG|JSON_HEX_APOS|JSON_HEX_AMP);
    } else {
      echo '"' . htmlEncode($key) . '":"' . htmlEncodeJson($value) . '"';
    }
  }
  echo '}';
} else {
  echo '{"error":"' . i18n('projectNotFound') . '"}';
}
?>
