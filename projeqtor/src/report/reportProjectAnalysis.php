<?php
require_once "../tool/projeqtor.php";
include_once('../tool/formatter.php');

$paramProject=pq_trim(RequestHandler::getId('idProject',false));
$headerParameters="";
if ($paramProject!="") {
  $headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project', $paramProject)) . '<br/>';
}

include "header.php";

$as=new Assumption();
$cs=new Constraint();
$ll=new LessonLearned();
$crit=array();

$queryWhere="";
if ($paramProject!="") {
  $queryWhere.="idProject in " . getVisibleProjectsList(true, $paramProject);
}

echo '<table style="width:95%;"align="center"'.excelName(i18n('menuProjectAnalysis')).'>';
// ==========Assumption=========
$asList=$as->getSqlElementsFromCriteria(null, false, $queryWhere);
echo '<tr>';
echo '<td class="reportTableHeader" style="width:5%; max-width:20px;" '.excelFormatCell('header',10).'>'.i18n('colId').'</td>';
echo '<td class="reportTableHeader" style="width:5%; max-width:50px" '.excelFormatCell('header',15).'>'.i18n('colType').'</td>';
echo '<td class="reportTableHeader" style="width:5%; max-width:50px" '.excelFormatCell('header',15).'>'.i18n('colIdProject').'</td>';
echo '<td class="reportTableHeader" style="width:10%; max-width:50px" '.excelFormatCell('header',50).'>'.i18n('colName').'</td>';
echo '<td class="reportTableHeader" style="width:5%; max-width:50px" '.excelFormatCell('header',15).'>'.i18n('colIdStatus').'</td>';
echo '<td class="reportTableHeader" style="width:5%; max-width:50px" '.excelFormatCell('header',15).'>'.i18n('colIdSeverity').'</td>';
echo '<td class="reportTableHeader" style="width:5%; max-width:50px" '.excelFormatCell('header',15).'>'.i18n('colIdLikelihood').'</td>';
echo '<td class="reportTableHeader" style="width:20%" '.excelFormatCell('header',60).'>'.i18n('colImpact').'</td>';
echo '<td class="reportTableHeader" style="width:20%" '.excelFormatCell('header',60).'>'.i18n('colActionPlan').'</td>';
echo '</tr>';


  foreach ($asList as $as) {
    echo '<tr>';
        echo '<td align="center" class="reportTableData" '.excelFormatCell('data').'>'.htmlEncode($as->id).'</td>';
        echo '<td align="center" style="width:50px; white-space:normal" class="reportTableData" '.excelFormatCell('data').'>'.i18n('Assumption').'</td>';
        echo '<td align="center" style="width:50px; white-space:normal" class="reportTableData" '.excelFormatCell('data').'>'.SqlList::getNameFromId('Project', $as->idProject).'</td>';
        echo '<td align="center" style="width:50px; white-space:normal" class="reportTableData" '.excelFormatCell('data').'>'.htmlEncode($as->name).'</td>';
      if($outMode == 'excel'){
         $status = new Status($as->idStatus);
         $color = $status->color;
         $foreColor = excelForeColorFormatColor($color);
          echo'<td  align="center" class="reportTableData"  '.excelFormatCell('data',15,$foreColor,$color).'>';
          echo $status->name.'</td>';
         
         $severity = new Severity($as->idSeverity);
         $color = $severity->color;
         $foreColor = excelForeColorFormatColor($color);
          echo'<td  align="center" class="reportTableData"  '.excelFormatCell('data',15,$foreColor,$color).'>';
          echo $severity->name.'</td>'; 
         
         $likelihood = new Likelihood($as->idLikelihood);
         $color = $likelihood->color;
         $foreColor = excelForeColorFormatColor($color);
          echo'<td  align="center" class="reportTableData"  '.excelFormatCell('data',15,$foreColor,$color).'>';
          echo $likelihood->name.'</td>';
      }else{
          echo'<td align="" style="width:20px;max-width:20px" class="reportTableData" ><div>'.formatColor('Status', $as->idStatus).'</div></td>';
          echo'<td align="" style="width:20px;max-width:20px" class="reportTableData" ><div>'.formatColor('Severity', $as->idSeverity).'</div></td>';
          echo'<td align="" style="width:20px;max-width:20px" class="reportTableData" ><div>'.formatColor('Likelihood', $as->idLikelihood).'</div></td>';
      }
      echo'<td align="" class="reportTableData" style="text-align:left;width:300px;max-width:300px" '.excelFormatCell('data').'>'.$as->impact.'</td>';
      echo'<td align="" class="reportTableData" style="text-align:left;width:300px;max-width:300px" '.excelFormatCell('data').'>'.$as->actionPlan.'</td>';
      echo'</tr>';
   }

   echo '<tr> <td colspan="9">&nbsp;</td> </tr>';
   // ==========Constriant=========
   $csList=$cs->getSqlElementsFromCriteria(null, false, $queryWhere);
   echo '<tr>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',10).'>'.i18n('colId').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',15).'>'.i18n('colType').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',15).'>'.i18n('colIdProject').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',50).'>'.i18n('colName').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',15).'>'.i18n('colIdStatus').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',15).'>'.i18n('colIdSeverity').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',15).'>'.i18n('colIdLikelihood').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',60).'>'.i18n('colImpact').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',60).'>'.i18n('colActionPlan').'</td>';
   echo '</tr>';

  foreach ($csList as $cs) {
    echo '<tr>';
        echo '<td align="center" class="reportTableData" '.excelFormatCell('data').'>'.htmlEncode($cs->id).'</td>';
        echo '<td align="center"  style="width:50px; white-space:normal" class="reportTableData" '.excelFormatCell('data').'>'.i18n('Constraint').'</td>';
        echo '<td align="center"  style="width:50px; white-space:normal" class="reportTableData" '.excelFormatCell('data').'>'.SqlList::getNameFromId('Project', $cs->idProject).'</td>';
        echo '<td align="center"  style="width:50px; white-space:normal" class="reportTableData" '.excelFormatCell('data').'>'.htmlEncode($cs->name).'</td>';
      if($outMode == 'excel'){
         $status = new Status($cs->idStatus);
         $color = $status->color;
         $foreColor = excelForeColorFormatColor($color);
          echo'<td  align="center" class="reportTableData"  '.excelFormatCell('data',15,$foreColor,$color).'>';
          echo $status->name.'</td>';
         
         $severity = new Severity($cs->idSeverity);
         $color = $severity->color;
         $foreColor = excelForeColorFormatColor($color);
          echo'<td  align="center" class="reportTableData"  '.excelFormatCell('data',15,$foreColor,$color).'>';
          echo $severity->name.'</td>'; 
         
         $likelihood = new Likelihood($cs->idLikelihood);
         $color = $likelihood->color;
         $foreColor = excelForeColorFormatColor($color);
          echo'<td  align="center" class="reportTableData"  '.excelFormatCell('data',15,$foreColor,$color).'>';
          echo $likelihood->name.'</td>';
      }else{
          echo'<td align="" class="reportTableData" style="width:20px;max-width:20px"><div>'.formatColor('Status', $cs->idStatus).'</div></td>';
          echo'<td align="" class="reportTableData" style="width:20px;max-width:20px"><div>'.formatColor('Severity', $cs->idSeverity).'</div></td>';
          echo'<td align="" class="reportTableData" style="width:20px;max-width:20px"><div>'.formatColor('Likelihood', $cs->idLikelihood).'</div></td>';
      }
      echo'<td align="" class="reportTableData" style="text-align:left;width:300px;max-width:300px" '.excelFormatCell('data').'>'.$cs->impact.'</td>';
      echo'<td align="" class="reportTableData" style="text-align:left;width:300px;max-width:300px" '.excelFormatCell('data').'>'.$cs->actionPlan.'</td>';
      echo'</tr>';
  }
   echo '<tr> <td colspan="9">&nbsp;</td> </tr>';
   // ==========LessonLearned=========
   $llList=$ll->getSqlElementsFromCriteria(null, false, $queryWhere);
   echo '<tr>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',10).'>'.i18n('colId').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',15).'>'.i18n('colType').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',15).'>'.i18n('colIdProject').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',50).'>'.i18n('colName').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',15).'>'.i18n('colIdStatus').'</td>';
     echo '<td class="reportTableHeader" colspan="3" style="width:30%;" '.excelFormatCell('header').'>'.i18n('colDescription').'</td>';
     echo '<td class="reportTableHeader" '.excelFormatCell('header',60).'>'.i18n('colActionPlan').'</td>';
   echo '</tr>';
   foreach ($llList as $ll) {
       echo '<tr>';
         echo '<td align="center" class="reportTableData" '.excelFormatCell('data').'>'.htmlEncode($ll->id).'</td>';
         echo '<td align="center" style="width:50px; white-space:normal" class="reportTableData" '.excelFormatCell('data').'>'.i18n('LessonLearned').'</td>';
         echo '<td align="center" style="width:50px; white-space:normal" class="reportTableData" '.excelFormatCell('data').'>'.SqlList::getNameFromId('Project', $ll->idProject).'</td>';
         echo '<td align="center" style="width:50px; white-space:normal" class="reportTableData" '.excelFormatCell('data').'>'.htmlEncode($ll->name).'</td>';
         if($outMode == 'excel'){
           $status = new Status($ll->idStatus);
           $color = $status->color;
           $foreColor = excelForeColorFormatColor($color);
           echo'<td  align="center" class="reportTableData"  '.excelFormatCell('data',20,$foreColor,$color).'>';
           echo $status->name.'</td>';
         }else{
           echo'<td align="" class="reportTableData" style="width:20px;max-width:20px" ><div>'.formatColor('Status', $ll->idStatus).'</div></td>';
         }
         echo'<td align="" class="reportTableData" style="text-align:left;width:400px;max-width:400px" colspan="3" '.excelFormatCell('data').'>'.$ll->description.'</td>';
         echo'<td align="" class="reportTableData" style="text-align:left;width:200px;max-width:200px" '.excelFormatCell('data').'>'.$ll->actionPlan.'</td>';
       echo'</tr>';
     }
end:   
echo '</table><br/>';
 
