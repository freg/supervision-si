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

  require_once "../tool/projeqtor.php";
  include_once('../tool/formatter.php');
//echo "workPerActivity.php";
// Creation of object "table"
  $objectClass='PlanningElement';
  $obj=new $objectClass();
  $table=$obj->getDatabaseTableName();
  $paramActivityType = pq_trim(RequestHandler::getId('idActivityType'));
  $scale=(RequestHandler::isCodeSet('scale'))?RequestHandler::getValue('scale'):null;
  if($scale=='twoDate'){
    $startDate=RequestHandler::isCodeSet('startDate')?RequestHandler::getValue("startDate"):null;
    $endDate=RequestHandler::isCodeSet('endDate')?RequestHandler::getValue("endDate"):null;
  }

  $print=false;
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
  if ($paramActivityType!="") {
    $headerParameters.= i18n("colIdActivityType") . ' : ' . htmlEncode(SqlList::getNameFromId('ActivityType', $paramActivityType)) . '<br/>';
  }
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

  // Preparation of query ///
  $querySelect = '';
  $queryFrom='';
  $queryWhere='';
  $queryOrderBy='';
  $idTab=0;
  if ($showIdle) {
    $queryWhere="1=1 ";
  }else{
    $queryWhere= $table . ".idle=0 ";
  }
//  if (! pq_array_key_exists('idle',$_REQUEST) ) {
//    $queryWhere= $table . ".idle=0 ";
//  }

  // Where clause
  $queryWhere.= ($queryWhere=='')?'':' and ';
  $queryWhere.=getAccesRestrictionClause('Activity',$table,false,true,true);
  if (pq_array_key_exists('idProject',$_REQUEST) and $_REQUEST['idProject']!=' ') {
	  $paramProject=pq_trim($_REQUEST['idProject']);
	  Security::checkValidId($paramProject);
    $queryWhere.= ($queryWhere=='')?'':' and ';
    $queryWhere.=  $table . ".idProject in " . getVisibleProjectsList(true, $paramProject) ;
  }

  // Select clause
  $querySelect .= $table . ".* ";

  // From clause
  $queryFrom .= $table;

  // Order By clause
  $queryOrderBy .= $table . ".wbsSortable ";

  // build of query
  $queryWhere=($queryWhere=='')?' 1=1':$queryWhere;
  $query='select ' . $querySelect
       . ' from ' . $queryFrom
       . ' where ' . $queryWhere
       . ' order by ' . $queryOrderBy;
  $result=Sql::query($query);

  // Test execution of query
  $test=array();
  if (Sql::$lastQueryNbRows > 0) $test[]="OK";
  if (checkNoData($test))  if (!empty($cronnedScript)) goto end; else exit;

  // Verify query result is not empty
  if (Sql::$lastQueryNbRows > 0) {

    // Headers of columns
    echo '<table align="center">';
    echo '<TR>';
    if($outMode!='excel')echo '  <TD class="reportTableHeader" style="width:10px; border-right: 0px;"></TD>';
    echo '  <TD class="reportTableHeader" style="width:200px; border-left:0px; text-align: left;" '.excelFormatCell('header',60).'>' . i18n('colTask') . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:60px" nowrap '.excelFormatCell('header',20).'>' . i18n('colValidated') . '</TD>' ;
    echo '  <TD class="reportTableHeader" style="width:60px" nowrap '.excelFormatCell('header',20).'>' . i18n('colAssigned') . '</TD>' ;
    echo '  <TD class="reportTableHeader" style="width:60px" nowrap '.excelFormatCell('header',20).'>' . i18n('colReal') . '</TD>' ;
    if($scale=='twoDate')echo '  <TD class="reportTableHeader" style="width:50px" nowrap '.excelFormatCell('header',20).'>' . i18n('colPeriodReal') . '</TD>' ;
    echo '  <TD class="reportTableHeader" style="width:60px" nowrap '.excelFormatCell('header',20).'>' . i18n('colLeft') . '</TD>' ;
    echo '  <TD class="reportTableHeader" style="width:60px" nowrap '.excelFormatCell('header',20).'>' . i18n('colReassessed') . '</TD>' ;
    echo '  <TD class="reportTableHeader" style="width:70px" nowrap '.excelFormatCell('header',20).'>' . i18n('progress') . '</TD>' ;
	echo '  <TD class="reportTableHeader" style="width:70px" nowrap '.excelFormatCell('header',20).'>Indicator</TD>' ;
    echo '</TR>';

    // Treat each line of result

    $alreadyExistingActivity=array();
    while ($line=Sql::fetchLine($result)) {
      $line=array_change_key_case($line,CASE_LOWER);
      $refType=$line["reftype"];
      $refId=$line["refid"];
      if ($paramActivityType and $refType=='Activity') {
        if (pq_array_key_exists($refId, $alreadyExistingActivity))
          $act = $alreadyExistingActivity[$refId]; 
        else {
          $act = new Activity($refId);
          $alreadyExistingActivity[$refId] = $act;
        }
        if ($refType == "Activity" && $paramActivityType != $act->idActivityType)continue;
      }
      
      if($scale=='twoDate'){
        $realWorkPeriod="0";
        $work= new Work();
        $pe=new PlanningElement();
        if($refType=="Project"){
          $proj=new Project($refId);
          $lstSubProject=$proj->getRecursiveSubProjectsFlatList(false,true);
          $critProjList='0';
          foreach ($lstSubProject as $tmpId=>$tmpName) $critProjList.=','.$tmpId;
          $where="workDate between '$startDate' and '$endDate' and idProject in ($critProjList)" ;
        }else{
//          $where="workDate between '$startDate' and '$endDate' and refType='".$refType."' and refId=".$refId;
          $listSub=Activity::getRecursiveSubActivitiesFlatList($line['refid']);
          $critId=($listSub)?$line['refid'].','.$listSub:$line['refid'];
          $where="workDate between '$startDate' and '$endDate' and refType='".$line['reftype']."' and refId in ($critId)";
        }
        $realWorkPeriod=$work->sumSqlElementsFromCriteria('work', null,$where);
      }
      
      
  	  // Store result elements
      $validatedWork=round(pq_nvl($line['validatedwork'],0),2);
      $assignedWork=round(pq_nvl($line['assignedwork'],0),2);
      $plannedWork=round(pq_nvl($line['plannedwork'],0),2);
      $realWork=round(pq_nvl($line['realwork'],0),2);
      $leftWork=round(pq_nvl($line['leftwork'],0),2);
      $progress=' 0';

      // Compute progress value
      if ($plannedWork>0) {
        $progress=round(100*$realWork/$plannedWork);
      } else {
        if ($line['done']) {
          $progress=100;
        }
      }

      // Check if activity has a parent one
          $pGroup=($line['elementary']=='0')?1:0;
      $compStyle=""; // complementary css style
	  $compStyleWarning=""; // complementary css style
	  $excelColor="";
	$indicator=""; // indicator for smiley

	  // Compare planned and assigned work
	  // Depending on result, display correspondong smiley
	  $indicator="neutral";
	  $excelBacgroundColor="#E8E80F";
	  if($plannedWork >$assignedWork) {
			$indicator="unhappy";
			$excelBacgroundColor="#FF1C32";
		  if( $pGroup) {
			$rowType = "group";
			$compStyle="font-weight: bold; background: #E8E8E8 ;";
		  } else if( $line['reftype']=='Milestone'){
			$rowType  = "mile";
			$compStyle="font-weight: light; font-style:italic;";
		  } else {
			$rowType  = "row";
			$compStyleWarning="color: #FF1C32 ;";
			$excelColor="#FF1C32";
		  }
	  }	 else if($plannedWork<$assignedWork) {
			$indicator="happy";
			$excelBacgroundColor="#65FF2D";
			if( $pGroup) {
			$rowType = "group";
			$compStyle="font-weight: bold; background: #E8E8E8 ;";
		  } else if( $line['reftype']=='Milestone'){
			$rowType  = "mile";
			$compStyle="font-weight: light; font-style:italic;";
		  } else {
			$rowType  = "row";
			$compStyleWarning="color: #65FF2D ;";
			$excelColor="#65FF2D";
		  }
		} else if($plannedWork == $assignedWork) {
			$indicator="neutral";
			$excelBacgroundColor="#E8E80F";
			if( $pGroup) {
			$rowType = "group";
			$compStyle="font-weight: bold; background: #E8E8E8 ;";
		  } else if( $line['reftype']=='Milestone'){
			$rowType  = "mile";
			$compStyle="font-weight: light; font-style:italic;";
		  } else {
			$rowType  = "row";
		  }
		}

      //________ draw by wbs ________//
      
      $wbs=$line['wbssortable'];
      $split=pq_explode('.', $wbs);
      $level=0;
      $testWbs='';
      foreach($split as $sp) {
        $testWbs.=(($testWbs)?'.':'').$sp;
        if (isset($levels[$testWbs])) $level=$levels[$testWbs]+1;
      }
      $levels[$wbs]=$level;
      $tab="";
      for ($j=1; $j<=$level; $j++) {
       $tab.='<span class="ganttSep">&nbsp;&nbsp;&nbsp;&nbsp;</span>';
      }
      
      echo '<TR>';
      if($outMode!='excel')echo '  <TD class="reportTableData" style="border-right:0px;' . $compStyle . '" ><img style="width:16px" src="../view/css/images/icon' . $line['reftype'] . '16.png" /></TD>';
      echo '  <TD class="reportTableData" style="border-left:0px; text-align: left;' . $compStyle . '" nowrap '.excelFormatCell(($pGroup?'subheader':'data'),null,null,null,null,'left').'>' 
            . $tab . (($outMode=='excel')?pq_htmlspecialchars($line['refname']):htmlEncode($line['refname'])) . '</TD>';
      
      echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,null,null,null,null,null,'work').'>'
           . Work::displayWorkWithUnit($validatedWork). '</TD>' ;
      
      echo '  <TD class="reportTableData" style="' . $compStyle."".$compStyleWarning . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,$excelColor,null,null,null,null,null,'work').'>' 
          . Work::displayWorkWithUnit($assignedWork) . '</TD>' ;
      
      echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,null,null,null,null,null,'work').'>' 
          . Work::displayWorkWithUnit($realWork) . '</TD>' ;
      
      if($scale=='twoDate'){
        echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,null,null,null,null,null,'work').'>'
            .Work::displayWorkWithUnit($realWorkPeriod) . '</TD>' ;
      }
      
      echo '  <TD class="reportTableData" style="' . $compStyle."".$compStyleWarning  . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,$excelColor,null,null,null,null,null,'work').'>' 
          . Work::displayWorkWithUnit($leftWork) . '</TD>' ;
      echo '  <TD class="reportTableData" style="' . $compStyle."".$compStyleWarning  . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,$excelColor,null,null,null,null,null,'work').'>' 
          . Work::displayWorkWithUnit($plannedWork) . '</TD>' ;
      echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,null,null,null,null,null,'percent').'>'  
          . percentFormatter($progress). '</TD>' ;
	  echo '  <TD class="reportTableData" style="border-right:0px;' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,$excelBacgroundColor).'><img style="width:16px" src="../view/css/images/indicator_' 
	           .(($outMode=='excel')?"":$indicator) . '.png" /></TD>';
      echo '</TR>';
    }
  }
  echo "</table>";
  
end:
  
?>