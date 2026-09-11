<?php 
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

include_once '../tool/projeqtor.php';
include_once '../tool/formatter.php';
include_once("../external/pChart2/class/pData.class.php");
include_once("../external/pChart2/class/pDraw.class.php");
include_once("../external/pChart2/class/pImage.class.php");

$idProject="";
if (pq_array_key_exists('idProject',$_REQUEST) and pq_trim($_REQUEST['idProject'])!="") {
  $idProject=pq_trim($_REQUEST['idProject']);
  $idProject = Security::checkValidId($idProject);
}

$headerParameters="";
if ($idProject!="") {
  $headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project',$idProject)) . '<br/>';
}


$graphWidth=1200;
$graphHeight=450;

include "header.php";

$projectHistory = new ProjectHistory();

$listHistory = $projectHistory->getSqlElementsFromCriteria(array('idProject'=>$idProject),false,null,'');

$arrayData=array();

foreach($listHistory as $hist) {
  $arrayData[$hist->day] = [$hist->realWork, $hist->leftWork];
}
ksort($arrayData); // PBER : to be sure to have data sorted
if (count($arrayData) >0) {
  $date = new DateTime(array_keys($arrayData)[0]);
  $lastDate = new DateTime(array_keys($arrayData)[count($arrayData)-1]);
  
  $globalData = array();
  
  $currentData=$arrayData[array_keys($arrayData)[0]];
  $dateArray=array();
  $realArray=array();
  $leftArray=array();
  while ($date <= $lastDate) {
    $day=$date->format('Ymd');
    if (isset($arrayData[$day])) $currentData=$arrayData[$day];
    $globalData[$date->format('Y-m-d')] = $currentData;
    $dateArray[]=htmlFormatDate($date->format('Y-m-d'));
    $realArray[]=$currentData[0];
    $leftArray[]=$currentData[1];
    $date->modify('+1 day');
  }
  $modulo=intVal(50*count($globalData)/$graphWidth);
  if ($modulo<0.5) $modulo=0;
  
  $dataSet = new pData();
//   $dataSet->addPoints(null, i18n('real'));
//   $dataSet->addPoints(null, i18n('left'));
//   $dataSet->addPoints(null, "days");
//   foreach($globalData as $dateTemp=>$dataTemp) {
//     $dataSet->addPoints($dataTemp[0] -1, i18n('real'));
//     $dataSet->addPoints($dataTemp[1], i18n('left'));
//     $dataSet->addPoints($dateTemp, "days");
//   }
  $dataSet->addPoints($realArray, 'real');
  $dataSet->addPoints($leftArray, 'left');
  $dataSet->addPoints($dateArray, 'days');
  $dataSet->setAbscissa('days');
  
  $dataSet->setAxisName(0, i18n("charge"));
  
  $dataSet->setSerieDescription("days", "dates");
  $dataSet->setSerieDescription("real", i18n('real'));
  $dataSet->setSerieDescription("left", i18n('left'));
  
  $realSettings = array("R"=>68,"G"=>115,"B"=>197);
  $leftSettings = array("R"=>237,"G"=>125,"B"=>49);
  $dataSet->setPalette('real',$realSettings);
  $dataSet->setPalette('left',$leftSettings);
  
  $graph = new pImage($graphWidth,$graphHeight,$dataSet);
  
  $graph->setFontProperties(array("FontName"=>getFontLocation("verdana"),"FontSize"=>9,"R"=>50,"G"=>50,"B"=>50));
  $graph->setGraphArea(60,20,$graphWidth-50,$graphHeight-100);
  
  $formatGrid=array("XMargin"=>0, "YMargin"=>0, "LabelSkip"=>$modulo, "SkippedAxisAlpha"=>(($modulo>9)?0:20), "SkippedGridTicks"=>0,
      "Mode"=>SCALE_MODE_ADDALL_START0, "GridTicks"=>0,"DrawYLines"=>array(0), "DrawXLines"=>true,"Pos"=>SCALE_POS_LEFTRIGHT,
      "LabelRotation"=>60,"DrawSubTicks"=>TRUE);
  $graph->drawScale($formatGrid);  
  $graph->Antialias = TRUE;
  $graph->drawStackedAreaChart(array("DisplayColor"=>DISPLAY_AUTO,"ForceTransparency"=>100));

  $graph->setShadow(FALSE);
  
  $graph->drawLegend($graphWidth/2,$graphHeight-10,array("Style"=>LEGEND_NOBORDER,"Mode"=>LEGEND_HORIZONTAL));
  
  $imgName=getGraphImgName("workloadhistory");
  $graph->Render($imgName);
  
  echo '<br/><br/><br/>';
  echo '<table width="95%" align="center"><tr><td align="center">';
  echo '<img style="width:'.$graphWidth.'px;height:'.$graphHeight.'" src="'.$imgName.'" />';
  echo '</td></tr></table>';
  echo '<br/>';
} else { 
	echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  echo i18n('reportNoData');
  echo '</div>';
}
