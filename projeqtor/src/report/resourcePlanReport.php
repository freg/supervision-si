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
  include_once('../tool/formatter.php');
//echo "workPlan.php";

  $objectClass='PlanningElement';
  $print=false;
  $showProject=true;
  $showIdleProjects=(sessionValueExists('projectSelectorShowIdle') and getSessionValue('projectSelectorShowIdle')==1)?1:0;
  $scale=(RequestHandler::isCodeSet('scale'))?RequestHandler::getValue('scale'):null;
  if($scale=='twoDate'){
    $startDate=RequestHandler::isCodeSet('startDate')?RequestHandler::getValue("startDate"):null;
    $endDate=RequestHandler::isCodeSet('endDate')?RequestHandler::getValue("endDate"):null;
  }
  if ( pq_array_key_exists('print',$_REQUEST) ) {
    $print=true;
  }

  // Header
  $headerParameters="";
  if (pq_array_key_exists('idProject',$_REQUEST) and pq_trim($_REQUEST['idProject'])!="") {
	$paramProject=pq_trim($_REQUEST['idProject']);
	Security::checkValidId($paramProject);

    $headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project', $paramProject)) . '<br/>';
  }
  //gautier ticket #2354
  $showIdle=false;
  
  if (pq_array_key_exists('showIdle',$_REQUEST)) {
    $showIdle=true;
    $headerParameters.= i18n("labelShowIdle").'<br/>';
  }
  if($scale=='twoDate'){
    if($startDate)$headerParameters.= i18n("startDate") . ' : ' . htmlFormatDate($startDate) . '<br/>';
    if($endDate)$headerParameters.= i18n("endDate") . ' : ' . htmlFormatDate($endDate) . '<br/>';
  }
  
  if (isset($outMode) and $outMode=='excel') {
    $headerParameters.=pq_str_replace('- ','<br/>',Work::displayWorkUnit()).'<br/>';
  }
  
  include "header.php";

  $accessRightRead=securityGetAccessRight('menuProject', 'read');
  
  $table=array();
  $specific="imputation";
  $includePool=true;
  $notDrawSelect=true;
  include("../tool/drawResourceListForSpecificAccess.php");
  $allowedResource=$table;
  
  $rta=new ResourceTeamAffectation();
  $today=date('Y-m-d');
  
  // ADD RESOURCES OF SELECTED POOL
  foreach ($allowedResource as $resId=>$resName) {
  	$rtaList=$rta->getSqlElementsFromCriteria(array('idResourceTeam'=>$resId));
  	foreach ($rtaList as $rta) {
  		if ($rta->idle) continue;
  		if ($rta->endDate==null or $rta->endDate>=$today) {
  			if (!isset($allowedResource[$rta->idResource])) $allowedResource[$rta->idResource]=SqlList::getNameFromId('ResourceAll', $rta->idResource);
  		}
  	}
  }
  
  // ADD POOLS OF SELECTED RESOURCES
  foreach ($allowedResource as $resId=>$resName) {
  	$rtaList=$rta->getSqlElementsFromCriteria(array('idResource'=>$resId));
  	foreach ($rtaList as $rta) {
  		if ($rta->idle) continue;
  		if ($rta->endDate==null or $rta->endDate>=$today) {
  			if (!isset($allowedResource[$rta->idResourceTeam])) $allowedResource[$rta->idResourceTeam]=SqlList::getNameFromId('ResourceAll', $rta->idResourceTeam);
  		}
  	}
  }
  
  $obj=new $objectClass();
  $table=$obj->getDatabaseTableName();
  $columnsDescription=Parameter::getPlanningColumnDescription();
  
  $querySelect = '';
  $queryFrom='';
  $queryWhere='';
  $queryOrderBy='';
  $idTab=0;
  
if ($showIdle) {
	$queryWhere ="1=1 ";
}else{
	$queryWhere= $table . ".idle=0 ";
}
$queryWhere.= ($queryWhere=='')?'':' and ';
$queryWhere.=getAccesRestrictionClause('Activity',$table,$showIdleProjects);

if ( pq_array_key_exists('report',$_REQUEST) ) {
	if (pq_array_key_exists('idProject',$_REQUEST) and $_REQUEST['idProject']!=' ') {
		$queryWhere.= ($queryWhere=='')?'':' and ';
		$queryWhere.=  $table . ".idProject in " . getVisibleProjectsList(! $showIdleProjects, $_REQUEST['idProject']) ;
	}
} else {
	$queryWhere.= ($queryWhere=='')?'':' and ';
	$queryWhere.=  $table . ".idProject in " . getVisibleProjectsList(! $showIdleProjects) ;
}

$queryWhere.=" and ass.idResource in ".transformListIntoInClause($allowedResource);

// Remove administrative projects :
$queryWhere.= ($queryWhere=='')?'':' and ';
$queryWhere.=  $table . ".idProject not in " . Project::getAdminitrativeProjectList() ;
$ass=new Assignment();
$res=new Resource();
$querySelect .= "pe.idProject as idProj, pe.id idPe, pe.wbs wbs, pe.wbsSortable wbsSortable, pe.priority priority, pe.idplanningmode idplanningmode, pe.validatedenddate, pe.notplannedwork  , pe.plannedenddate as peplannedend, pe.plannedstartdate as peplannedstart, pe.color as color, ass.* , usr.fullName as name, pe.refName refName";
$querySelect .= ", pe.topRefType as topreftype, pe.toprefid as toprefid, pe.topid as topid ";
$queryFrom .= $table . ' pe, ' . $ass->getDatabaseTableName() . ' ass, ' . $res->getDatabaseTableName() . ' usr';
$queryWhere= ' pe.refType=ass.refType and pe.RefId=ass.refId and usr.id=ass.idResource and ' . pq_str_replace($table, 'pe', $queryWhere);
$queryOrderBy .= ' name, pe.wbsSortable ';


  // constitute query and execute
  $query='select ' . $querySelect
       . ' from ' . $queryFrom
       . ' where ' . $queryWhere
       . ' order by ' . $queryOrderBy;
  
  $result=Sql::query($query);

  $list=array();
  $idResource="";
  $idProject="";
  $sumAssigned=0;
  $sumReal=0;
  $sumLeft=0;
  $sumPlanned=0;
  $sumProjAssigned=0;
  $sumProjReal=0;
  $sumProjLeft=0;
  $sumProjPlanned=0;
  $keyProj="";
  $idProj='';
  $keyRes="";
  $idRes='';
  $cptLine=0;
  
  $arrayPeAss=array();
  $arrayResource=array();
  $arrayProject=array();
  $nbRows=0;
  
  while ($line = Sql::fetchLine($result)) {
  	$line=array_change_key_case($line,CASE_LOWER);
  	//florent 4391
  	if (! isset($allowedResource[$line['idresource']])) continue;
  	$cptLine++;
  	if ($line['idresource']!=$idResource) {
  		$idResource=$line['idresource'];
  		$arrayResource[$idResource]=array();;
  		$resAr=array();
  		$resAr["refname"]=$line['name'];
  		$res=new ResourceAll($idResource,true);
  		if ($res->isResourceTeam) {
  			$resAr["reftype"]='ResourceTeam';
  		} else {
  			$resAr["reftype"]='Resource';
  		}
  		$resAr["refid"]=$idResource;
  		$resAr["elementary"]='0';
  		$idRes=$idResource*1000000;
  		$resAr["id"]=$idRes;
  		$resAr["idle"]='0';
  		$resAr["wbs"]='';
  		$resAr["wbssortable"]='';
  		$resAr["realstartdate"]='';
  		$resAr["realenddate"]='';
  		$resAr["plannedstartdate"]='';
  		$resAr["plannedenddate"]='';
  		$resAr["idresource"]=$idResource;
  		$resAr["progress"]=0;
  		$resAr["topid"]=0;
  		$resAr["leftwork"]=0;
  		$resAr["priority"]="";
  		$resAr["planningmode"]="";
  		$keyRes='Resource#'.$idResource;
  		$list[$keyRes]=$resAr;
  		//$sumValidated=0;
  		$sumAssigned=0;
  		$sumReal=0;
  		$sumLeft=0;
  		$sumPlanned=0;
  		$idProject="";
  	}
  	if ($showProject and $line['idproj']!=$idProject) {
  		$idProject=$line['idproj'];
  		if (pq_array_key_exists($idProject, $arrayProject)) {
  			$prj=$arrayProject[$idProject];
  		} else {
  			$prj=new Project($idProject,false);
  			$arrayProject[$idProject]=$prj;
  		}
  		$resPr=array();
  		$resPr["refname"]=$prj->name;
  		$resPr["reftype"]='Project';
  		$resPr["refid"]=$idProject;
  		$resPr["elementary"]='0';
  		$idProj=$idRes+$idProject;
  		$resPr["id"]=$idProj;
  		$resPr["idle"]='0';
  		$resPr["wbs"]=$prj->ProjectPlanningElement->wbs;
  		$resPr["wbssortable"]=$prj->ProjectPlanningElement->wbsSortable;
  		$resPr["realstartdate"]='';
  		$resPr["realenddate"]='';
  		$resPr["plannedstartdate"]='';
  		$resPr["plannedenddate"]='';
  		$resPr["idresource"]=$idResource;
  		$resPr["progress"]=0;
  		$resPr["topid"]=$idRes;
  		$resPr["leftwork"]=0;
  		$resPr["priority"]="";
  		$resPr["planningmode"]="";
  		$keyProj=$keyRes.'_Project#'.$idProject;
  		$list[$keyProj]=$resPr;
  		//$sumValidated=0;
  		$sumProjAssigned=0;
  		$sumProjReal=0;
  		$sumProjLeft=0;
  		$sumProjPlanned=0;
  	}
  	$line["elementary"]='1';
  	if (!isset($line["id"])) $line["id"]=$line["idpe"];
  	if ($line['reftype']=='Meeting' and $line['topreftype']=='PeriodicMeeting') {
  		//Do not change topRefType  ;
  		$line['topid']=$line['topid'].'_'.$line['idresource'];
  	} else {
  		if ($line['reftype']=='PeriodicMeeting') {
  			$line["elementary"]='0'; // Will contain meetings
  			$line["id"]=$line["idpe"].'_'.$line['idresource'];
  		}
  		$line["topreftype"]=($showProject)?'Project':'Resource';
  		$line["toprefid"]=($showProject)?$idProject:$idResource;
  	}
  	$line["validatedworkdisplay"]='';
  	$line["assignedworkdisplay"]=Work::displayWorkWithUnit($line["assignedwork"]);
  	$line["realworkdisplay"]=Work::displayWorkWithUnit($line["realwork"]);
  	$line["leftworkdisplay"]=Work::displayWorkWithUnit($line["leftwork"]);
  	$line["plannedworkdisplay"]=Work::displayWorkWithUnit($line["plannedwork"]);
  	if (floatval($line['plannedwork'])==0 and pq_trim($line['plannedstartdate'])=='' and pq_trim($line['peplannedstart'])!='') { $line['plannedstartdate']=$line['peplannedstart'];}
  	if (floatval($line['plannedwork'])==0 and pq_trim($line['plannedenddate'])=='' and pq_trim($line['peplannedend'])!='') { $line['plannedenddate']=$line['peplannedend'];}
  	if ($columnsDescription['IdStatus']['show']==1 or $columnsDescription['Type']['show']==1) {
  		$ref=$line['reftype'];
  		$type='id'.$ref.'Type';
  		$item=new $ref($line['refid'],true);
  		$line["status"]=(property_exists($item,'idStatus'))?SqlList::getNameFromId('Status',$item->idStatus)."#split#".SqlList::getFieldFromId('Status',$item->idStatus,'color'):null;
  		$line["type"]=(property_exists($item,$type))?SqlList::getNameFromId('Type',$item->$type):null;
  	}
  	if ($line['reftype']=='Meeting' and $line['topreftype']=='PeriodicMeeting') {
  		// topid from query
  	} else {
  		$line["topid"]=($showProject)?$idProj:$idRes;
  	}
  	if ($line["leftwork"]>0) {
  		//$line['realenddate']='';
  	}
  	if (pq_trim($line["realstartdate"]) and !pq_trim($line["plannedstartdate"])) {
  		$line['plannedstartdate']=$line['realstartdate'];
  	}
  	$line['progress']=($line["plannedwork"]>0)?round($line["realwork"]/$line["plannedwork"],2):'';
  	$line['planningmode']=SqlList::getNameFromId('PlanningMode', $line['idplanningmode']);
  	$list[]=$line;
  	//$sumValidated=0;
  	$sumAssigned+=$line["assignedwork"];
  	$sumReal+=$line["realwork"];
  	$sumLeft+=$line["leftwork"];
  	$sumPlanned+=$line["plannedwork"];
  	if (! $list[$keyRes]["realstartdate"] or $line['realstartdate'] < $list[$keyRes]["realstartdate"]) {
  		if ($line['realstartdate'] and $line['realstartdate']<$line['plannedstartdate']) {
  			$list[$keyRes]["realstartdate"]=$line['realstartdate'];
  		}
  	}
  	if (! $list[$keyRes]["realenddate"] or $line['realenddate'] > $list[$keyRes]["realenddate"]) {
  		if ($line['realenddate'] and $line['realenddate']>$line['plannedenddate']) {
  			$list[$keyRes]["realenddate"]=$line['realenddate'];
  		}
  	}
  	if (! $list[$keyRes]["plannedstartdate"] or $line['plannedstartdate'] < $list[$keyRes]["plannedstartdate"]) {
  		if ($line['plannedstartdate'] ) {
  			$list[$keyRes]["plannedstartdate"]=$line['plannedstartdate'];
  		}
  	}
  	if (! $list[$keyRes]["plannedenddate"] or $line['plannedenddate'] > $list[$keyRes]["plannedenddate"]) {
  		if ($line['plannedenddate']) {
  			$list[$keyRes]["plannedenddate"]=$line['plannedenddate'];
  			if ($list[$keyRes]["plannedenddate"]>$list[$keyRes]["realenddate"]) {
  				$list[$keyRes]["realenddate"]="";
  			}
  		}
  	}
  	$list[$keyRes]["assignedwork"]=$sumAssigned;
  	$list[$keyRes]["realwork"]=$sumReal;
  	$list[$keyRes]["leftwork"]=$sumLeft;
  	$list[$keyRes]["plannedwork"]=$sumPlanned;
  	$list[$keyRes]["validatedworkdisplay"]='';
  	$list[$keyRes]["assignedworkdisplay"]=Work::displayWorkWithUnit($sumAssigned);
  	$list[$keyRes]["realworkdisplay"]=Work::displayWorkWithUnit($sumReal);
  	$list[$keyRes]["leftworkdisplay"]=Work::displayWorkWithUnit($sumLeft);
  	$list[$keyRes]["plannedworkdisplay"]=Work::displayWorkWithUnit($sumPlanned);
  	$list[$keyRes]["progress"]=($sumPlanned>0)?round($sumReal/$sumPlanned,2):0;
  	$list[$keyRes]["status"]="";
  	$list[$keyRes]["type"]="";
  	if ($showProject) {
  		$sumProjAssigned+=$line["assignedwork"];
  		$sumProjReal+=$line["realwork"];
  		$sumProjLeft+=$line["leftwork"];
  		$sumProjPlanned+=$line["plannedwork"];
  		$list[$keyProj]["assignedwork"]=$sumProjAssigned;
  		$list[$keyProj]["realwork"]=$sumProjReal;
  		$list[$keyProj]["leftwork"]=$sumProjLeft;
  		$list[$keyProj]["plannedwork"]=$sumProjPlanned;
  		$list[$keyProj]["assignedworkdisplay"]=Work::displayWorkWithUnit($sumProjAssigned);
  		$list[$keyProj]["realworkdisplay"]=Work::displayWorkWithUnit($sumProjReal);
  		$list[$keyProj]["leftworkdisplay"]=Work::displayWorkWithUnit($sumProjLeft);
  		$list[$keyProj]["plannedworkdisplay"]=Work::displayWorkWithUnit($sumProjPlanned);
  		$list[$keyProj]["progress"]=($sumProjPlanned)?round($sumProjReal/$sumProjPlanned,2):0;
  		if ($columnsDescription['IdStatus']['show']==1 or $columnsDescription['Type']['show']==1 or $columnsDescription['Priority']['show']==1) {
  			$item=new Project($line['idproject'],false);
  			$list[$keyProj]["status"]=SqlList::getNameFromId('Status',$item->idStatus)."#split#".SqlList::getFieldFromId('Status',$item->idStatus,'color');
  			$list[$keyProj]["type"]=SqlList::getNameFromId('Type',$item->idProjectType);
  			//$list[$keyProj]["priority"]=SqlList::getNameFromId('Priority',$item->ProjectPlanningElement->priority);
  			$list[$keyProj]["priority"]=$item->ProjectPlanningElement->priority;
  		}
  		if (! $list[$keyProj]["realstartdate"] or $line['realstartdate'] < $list[$keyProj]["realstartdate"]) {
  			if ($line['realstartdate'] and $line['realstartdate']<$line['plannedstartdate']) {
  				$list[$keyProj]["realstartdate"]=$line['realstartdate'];
  			}
  		}
  		if (! $list[$keyProj]["realenddate"] or $line['realenddate'] > $list[$keyProj]["realenddate"]) {
  			if ($line['realenddate'] and $line['realenddate']>$line['plannedenddate']) {
  				$list[$keyProj]["realenddate"]=$line['realenddate'];
  			}
  		}
  		if (! $list[$keyProj]["plannedstartdate"] or $line['plannedstartdate'] < $list[$keyProj]["plannedstartdate"]) {
  			if ($line['plannedstartdate'] ) {
  				$list[$keyProj]["plannedstartdate"]=$line['plannedstartdate'];
  			}
  		}
  		if (! $list[$keyProj]["plannedenddate"] or $line['plannedenddate'] > $list[$keyProj]["plannedenddate"]) {
  			if ($line['plannedenddate']) {
  				$list[$keyProj]["plannedenddate"]=$line['plannedenddate'];
  				if ($list[$keyProj]["plannedenddate"]>$list[$keyProj]["realenddate"]) {
  					$list[$keyProj]["realenddate"]="";
  				}
  			}
  		}
  	}
  	if (! isset($arrayPeAss[$line['idpe']])) {
  		$arrayPeAss[$line['idpe']]=array();
  	}
  	$arrayPeAss[$line['idpe']][$line['id']]=$line['id'];
  	$arrayResource[$idResource][$line['id']]=$line['id'];
  }
  $resultArray=array();
  foreach ($list as $line) {
  	$pStart="";
  	$pStart=(pq_trim($line['plannedstartdate'])!="")?$line['plannedstartdate']:$pStart;
  	$pStart=(pq_trim($line['realstartdate'])!="")?$line['realstartdate']:$pStart;
  	if (pq_trim($line['plannedstartdate'])!=""
  			and pq_trim($line['realstartdate'])!=""
  					and $line['plannedstartdate']<$line['realstartdate'] ) {
  		$pStart=$line['plannedstartdate'];
  	}
  	$pEnd="";
  	$pEnd=(pq_trim($line['plannedenddate'])!="")?$line['plannedenddate']:$line['realenddate'];
  	$pEnd=(pq_trim($line['plannedenddate'])=="" and pq_trim($line['realenddate'])!="")?$line['realenddate']:$pEnd;
  	if ($line['reftype']=='Milestone') {
  		$pStart=$pEnd;
  	}
  	$line['pstart']=$pStart;
  	$line['pend']=$pEnd;
  	$line['prealend']=$line['realenddate'];
  	$line['pplanstart']=$line['plannedstartdate'];
  	$resultArray[]=$line;
  }
  // Header
  echo '<table align="center" '.excelName().'>';
  echo '<TR>';
  if($outMode!='excel')echo '  <TD class="reportTableHeader" style="width:10px; border-right: 0px;" '.excelFormatCell('header',10).'></TD>';
  echo '  <TD class="reportTableHeader" style="width:200px; border-left:0px; text-align: left;" '.excelFormatCell('header',100).'>' . i18n('colTask') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:50px" '.excelFormatCell('header',12).'>' . i18n('colAssigned') . '</TD>' ;
  echo '  <TD class="reportTableHeader" style="width:50px" '.excelFormatCell('header',12).'>' . i18n('colReal') . '</TD>' ;
  echo '  <TD class="reportTableHeader" style="width:50px" '.excelFormatCell('header',12).'>' . i18n('colLeft') . '</TD>' ;
  echo '  <TD class="reportTableHeader" style="width:50px" '.excelFormatCell('header',12).'>' . i18n('colReassessed') . '</TD>' ;
  echo '  <TD class="reportTableHeader" style="width:30px" '.excelFormatCell('header',12).'>' . i18n('colDuration') . '</TD>' ;
  echo '  <TD class="reportTableHeader" style="width:70px" '.excelFormatCell('header',15).'>' . i18n('progress') . '</TD>' ;
  echo '</TR>';
  // Treat each line
  foreach ($resultArray as $line) {
  	$pEnd=$line['pend'];
  	$pStart=$line['pstart'];
  	$pRealEnd=$line['prealend'];
  	$pPlanStart=$line['pplanstart'];
  	$realWork=$line['realwork'];
  	$plannedWork=$line['plannedwork'];
  	$progress=$line['progress'];
  	// pGroup : is the tack a group one ?
  	$pGroup=($line['reftype']=='Resource' or $line['reftype']=='ResourceTeam' or $line['reftype']=='Project')?1:0;
  	$scope='Planning_'.$line['reftype'].'_'.$line['refid'];
  	$compStyle="";
  	$bgColor="";
  	$bold=false;
  	if( $pGroup) {
  		$rowType = "group";
  		$compStyle="font-weight: bold;";
  		$bgColor=($line['reftype']=='Resource' or $line['reftype']=='ResourceTeam')?'#b8b8e5':"#E8E8E8";
  		$bold=true;
  		$compStyle .= "background:$bgColor;";
  	} else if( $line['reftype']=='Milestone'){
  		$rowType  = "mile";
  	} else {
  		$rowType  = "row";
  	}
  	$wbs=$line['wbssortable'];
  	if ($line['reftype']=='Resource' or $line['reftype']=='ResourceTeam') {
  		$level=1;
  	} else if ($line['reftype']=='Project') {
  		$level=2;
  	} else if ($showProject) {
  		$level=3;
  	} else {
  		$level=2;
  	}
  	$tab="";
  	for ($i=1;$i<$level;$i++) {
  		$tab.='<span class="ganttSep">&nbsp;&nbsp;&nbsp;&nbsp;</span>';
  	}
  	$pName="";
  	$pName.=htmlEncode($line['refname']);
  	$durationDisplay=($rowType=='mile' or $pStart=="" or $pEnd=="")?'-':workDayDiffDates($pStart, $pEnd) . "&nbsp;" . i18n("shortDay");
  	$duration=($rowType=='mile' or $pStart=="" or $pEnd=="")?0:workDayDiffDates($pStart, $pEnd);
  	$compStyle.="white-space:nowrap;";
  	echo '<TR>';
  	if($outMode!='excel')echo '<TD class="reportTableData" style="border-right:0px;' . $compStyle . '">'.formatIcon($line['reftype'], 16).'</TD>';
  	echo '  <TD class="reportTableData" style="border-left:0px; text-align: left;' . $compStyle . '" nowrap '.excelFormatCell(($pGroup?'subheader':'data'),null,null,$bgColor,$bold,'left').'>' . $tab .(($outMode=='excel')?pq_htmlspecialchars($line['refname']):htmlEncode($line['refname'])) . '</TD>';
	  echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup)?'subheader':'data',null,null,$bgColor,$bold,'center',null,null,'work').'>' .  (($outMode=='excel')?round(floatval($line["assignedwork"]),2):Work::displayWorkWithUnit($line["assignedwork"])) . '</TD>' ;
		echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup)?'subheader':'data',null,null,$bgColor,$bold,'center',null,null,'work').'>' . (($outMode=='excel')?round(floatval($line["realwork"]),2):Work::displayWorkWithUnit($line["realwork"]))  . '</TD>' ;
		echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup)?'subheader':'data',null,null,$bgColor,$bold,'center',null,null,'work').'>' . (($outMode=='excel')?round(floatval($line["leftwork"]),2):Work::displayWorkWithUnit($line["leftwork"]))  . '</TD>' ;
		echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup)?'subheader':'data',null,null,$bgColor,$bold,'center',null,null,'work').'>' . (($outMode=='excel')?round(floatval($line["plannedwork"]),2):Work::displayWorkWithUnit($line["plannedwork"]))  . '</TD>' ;
		echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup)?'subheader':'data',null,null,$bgColor,$bold,'center',null,null,'work').'>' . (($outMode=='excel')?$duration:$durationDisplay)  . '</TD>' ;
		echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup)?'subheader':'data',null,null,$bgColor,$bold,'center',null,null,'percent').'>' . (($outMode=='excel')?round(floatval($progress),2):percentFormatter(round(floatval($progress)*100))) . '</TD>' ;
  	echo '</TR>';
  }
echo "</table>";
  
end:
  
?>