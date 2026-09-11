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
  $obj=new $objectClass();
  $table=$obj->getDatabaseTableName();
  $print=false;
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

  $querySelect = '';
  $queryFrom='';
  $queryWhere='';
  $queryOrderBy='';
  $idTab=0;
//   if (! pq_array_key_exists('idle',$_REQUEST) ) {
//     $queryWhere= $table . ".idle=0 ";
//   }
  //gautier ticket #2354
  if ($showIdle) {
    $queryWhere ="1=1 ";
  }else{
    $queryWhere= $table . ".idle=0 ";
  }
  $queryWhere.= ($queryWhere=='')?'':' and ';
  $queryWhere.=getAccesRestrictionClause('Activity',$table,false,true,true);
  if (pq_array_key_exists('idProject',$_REQUEST) and $_REQUEST['idProject']!=' ') {
	  $paramProject=pq_trim($_REQUEST['idProject']);
	  Security::checkValidId($paramProject);
    $queryWhere.= ($queryWhere=='')?'':' and ';
    $queryWhere.=  $table . ".idProject in " . getVisibleProjectsList(true, $paramProject) ;
  }

  $querySelect .= $table . ".* ";
  $queryFrom .= $table;
  $queryOrderBy .= $table . ".wbsSortable ";

  // constitute query and execute
  $query='select ' . $querySelect
       . ' from ' . $queryFrom
       . ' where ' . $queryWhere
       . ' order by ' . $queryOrderBy;
  $result=Sql::query($query);
  $test=array();
  if (Sql::$lastQueryNbRows > 0) $test[]="OK";
  if (checkNoData($test))  if (!empty($cronnedScript)) goto end; else exit;

  if (Sql::$lastQueryNbRows > 0) {
    // Header
    echo '<table align="center">';
    echo '<TR>';
    if($outMode!='excel')echo '  <TD class="reportTableHeader" style="width:10px; border-right: 0px;" ></TD>';
    echo '  <TD class="reportTableHeader" style="width:200px; border-left:0px; text-align: left;" '.excelFormatCell('header',100).'>' . i18n('colTask') . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:50px" nowrap '.excelFormatCell('header',12).'>' . i18n('colValidated') . '</TD>' ;
    echo '  <TD class="reportTableHeader" style="width:50px" nowrap '.excelFormatCell('header',12).'>' . i18n('colAssigned') . '</TD>' ;
    echo '  <TD class="reportTableHeader" style="width:50px" nowrap '.excelFormatCell('header',12).'>' . (($scale=='twoDate')?i18n('colTotalReal'):i18n('colReal')) . '</TD>' ;
    if($scale=='twoDate')echo '  <TD class="reportTableHeader" style="width:50px" nowrap '.excelFormatCell('header',12).'>' . i18n('colPeriodReal') . '</TD>' ;
    echo '  <TD class="reportTableHeader" style="width:50px" nowrap '.excelFormatCell('header',12).'>' . i18n('colLeft') . '</TD>' ;
    echo '  <TD class="reportTableHeader" style="width:50px" nowrap '.excelFormatCell('header',12).'>' . i18n('colReassessed') . '</TD>' ;
    echo '  <TD class="reportTableHeader" style="width:70px" nowrap '.excelFormatCell('header',15).'>' . i18n('progress') . '</TD>' ;
    echo '  <TD class="reportTableHeader" style="width:70px" nowrap '.excelFormatCell('header',15).'>' . i18n('colExpectedProgress') . '</TD>' ;
    echo '</TR>';
    // Treat each line
    while ($line = Sql::fetchLine($result)) {
    	$line=array_change_key_case($line,CASE_LOWER);
      $validatedWork=$line['validatedwork'];
      $assignedWork=$line['assignedwork'];
      $plannedWork=$line['plannedwork'];
      $realWork=$line['realwork'];
      $leftWork=$line['leftwork'];
      /*$progress=' 0';
      if ($plannedWork>0) {
        $progress=round(100*$realWork/$plannedWork);
      } else {
        if ($line['done']) {
          $progress=100;
        }
      }*/
      if($scale=='twoDate'){
        $realWorkPeriod=0;
        $work= new Work();
        $pe=new PlanningElement();
        if($line['reftype']=="Project"){
          $proj=new Project($line['refid'],true);
          $lstSubProject=$proj->getRecursiveSubProjectsFlatList(false,true);
          $where="workDate between '$startDate' and '$endDate' and idProject in (".implode(",", array_flip($lstSubProject)).")" ;
        }else{
          $listSub=Activity::getRecursiveSubActivitiesFlatList($line['refid']);
          $critId=($listSub)?$line['refid'].','.$listSub:$line['refid'];
          $where="workDate between '$startDate' and '$endDate' and refType='".$line['reftype']."' and refId in ($critId)";
        }
        $realWorkPeriod=$work->sumSqlElementsFromCriteria('work', null,$where);
      }
      $progress=$line['progress'];
      $expectedProgress=$line['expectedprogress'];
      // pGroup : is the tack a group one ?
      $pGroup=($line['elementary']=='0')?1:0;
      $compStyle="";
      $bgColor="";
      $bold=false;
      if( $pGroup) {
        $rowType = "group";
        $compStyle="font-weight: bold; background: #E8E8E8 ;";
        $bgColor="E8E8E8";
        $bold=true;
      } else if( $line['reftype']=='Milestone'){
        $rowType  = "mile";
        $compStyle="font-weight: light; font-style:italic;";
      } else {
        $rowType  = "row";
      }
//       $wbs=$line['wbssortable'];
//       $level=(pq_strlen($wbs)+1)/4;
//       $tab="";
//       for ($i=1;$i<$level;$i++) {
//         $tab.='<span class="ganttSep">&nbsp;&nbsp;&nbsp;&nbsp;</span>';
//       }
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
      $compStyle.="white-space:nowrap;";
      echo '<TR>';
      if($outMode!='excel')echo '  <TD class="reportTableData" style="border-right:0px;' . $compStyle . '" >'.formatIcon($line['reftype'], 16).'</TD>'; 
      echo '  <TD class="reportTableData" style="border-left:0px; text-align: left;' . $compStyle . '" nowrap '.excelFormatCell(($pGroup?'subheader':'data'),null,null,$bgColor,$bold,'left').'>' . $tab .(($outMode=='excel')?pq_htmlspecialchars($line['refname']):htmlEncode($line['refname'])) . '</TD>';
      echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,$bgColor,$bold,null,null,null,'work').'>' 
            . Work::displayWorkWithUnit($validatedWork)  . '</TD>' ;
      echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,$bgColor,$bold,null,null,null,'work').'>' 
            . Work::displayWorkWithUnit($assignedWork) . '</TD>' ;
      echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,$bgColor,$bold,null,null,null,'work').'>' 
            . Work::displayWorkWithUnit($realWork) . '</TD>' ;
      if($scale=='twoDate'){
        echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,$bgColor,$bold,null,null,null,'work').'>'
            .Work::displayWorkWithUnit($realWorkPeriod) . '</TD>' ;
      }
           
      echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,$bgColor,$bold,null,null,null,'work').'>' 
            . Work::displayWorkWithUnit($leftWork). '</TD>' ;
      echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,$bgColor,$bold,null,null,null,'work').'>' 
            . Work::displayWorkWithUnit($plannedWork) . '</TD>' ;
      echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,$bgColor,$bold,null,null,null,'percent').'>'  
          . percentFormatter($progress). '</TD>' ;
      echo '  <TD class="reportTableData" style="' . $compStyle . '" '.excelFormatCell(($pGroup?'subheader':'data'),null,null,$bgColor,$bold,null,null,null,'percent').'>'  
          . percentFormatter($expectedProgress). '</TD>' ;
      echo '</TR>';
    }
  }
  echo "</table>";
  
end:
  
?>