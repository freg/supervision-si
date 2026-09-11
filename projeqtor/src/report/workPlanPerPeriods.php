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

$startDate=RequestHandler::getValue("startDate");
$endDate=RequestHandler::getValue("endDate");
$idOrganization = pq_trim(RequestHandler::getId('idOrganization'));
$paramTeam='';
if (pq_array_key_exists('idTeam',$_REQUEST)) {
  $paramTeam=pq_trim($_REQUEST['idTeam']);
  Security::checkValidId($paramTeam);
}
$headerParameters="";
if ($idOrganization!="") {
  $headerParameters.= i18n("colIdOrganization") . ' : ' . htmlEncode(SqlList::getNameFromId('Organization',$idOrganization)) . '<br/>';
}
if ( $paramTeam) {
  $headerParameters.= i18n("team") . ' : ' . SqlList::getNameFromId('Team', $paramTeam) . '<br/>';
}
if($startDate)$headerParameters.= i18n("startDate") . ' : ' . htmlFormatDate($startDate) . '<br/>';
if($endDate)$headerParameters.= i18n("endDate") . ' : ' . htmlFormatDate($endDate) . '<br/>';

include "header.php";
  
$user=getSessionUser();
$queryWhere=getAccesRestrictionClause('Activity','t1',false,true,true);

if ($idOrganization ) {
  $orga = new Organization($idOrganization);
  $listResOrg=$orga->getResourcesOfAllSubOrganizationsListAsArray();
  $inClause='(0';
  foreach ($listResOrg as $res) {
    $inClause.=','.$res;
  }
  $inClause.=')';
  $queryWhere.= " and t1.idResource in ".$inClause;
}
if ($paramTeam) {
	$res=new ResourceAll();//florent ticket #5038
	$lstRes=$res->getSqlElementsFromCriteria(array('idTeam'=>$paramTeam));
	$inClause='(0';
	foreach ($lstRes as $res) {
		$inClause.=','.$res->id;
	}
	$inClause.=')';
	$queryWhere.= " and t1.idResource in ".$inClause;
}
$querySelect= 'select sum(work) as sumWork, t1.idResource as idresource, t1.idProject as idproject '; 
$queryGroupBy = 't1.idProject, t1.idResource';
// constitute query and execute

$queryWhere .= ($startDate)?"and t1.workdate >= '$startDate'":"";
$queryWhere .= ($endDate)?"and t1.workdate <= '$endDate'":"";
$start=$startDate;
$end=$endDate;

$tab=array();
$arrDates=array();
$arrProj=$user->getVisibleProjectsNullForeignKey(true);
$arrRes=array();
$arrSum=array('resource'=>array(), 'project'=>array());

$res=new Resource();
$resTable=$res->getDatabaseTableName();
$prj=new Project();
$prjTable=$prj->getDatabaseTableName();

foreach ($arrProj as $id=>$name){
  $prj = new Project($id);
  $code = SqlList::getFieldFromId('Type', $prj->idProjectType, 'code');
  if($code=='ADM')unset($arrProj[$id]);
}

for ($i=1;$i<=2;$i++) {
  $obj=($i==1)?new Work():new PlannedWork();
  $var=($i==1)?'real':'plan';
  $query=$querySelect 
     . ' from ' . $obj->getDatabaseTableName().' t1, '.$resTable.' t2, '.$prjTable.' t3'
     . ' where '.$queryWhere.' and t1.idResource=t2.id and t1.idProject=t3.id '
     . ' group by ' . $queryGroupBy;
  $result=Sql::query($query);
  while ($line = Sql::fetchLine($result)) {
  	$line=array_change_key_case($line,CASE_LOWER);
    $res=$line['idresource'];
    $proj=$line['idproject'];
    $work=$line['sumwork'];
    if (!isset($tab[$proj][$res])) {
      $tab[$proj][$res]=array("real"=>0,"plan"=>0);
    }
    if(!isset($tab[$proj][$res][$var])){
      $tab[$proj][$res][$var]=0;
    }else{
      $tab[$proj][$res][$var]+=floatval($work);
    }
    if(isset($arrProj[$proj])){
      $prj = new Project($proj);
      $code = SqlList::getFieldFromId('Type', $prj->idProjectType, 'code');
      if($code=='ADM')unset($arrProj[$proj]);
    }
    $arrRes[$res]=SqlList::getNameFromId('Affectable', $res);
  }
}
if (checkNoData($tab)) if (!empty($cronnedScript)) goto end; else exit;

// Header
$plannedBGColor='#FFFFDD';
$plannedFrontColor='#777777';
$styleRed=' style="color:#d05050;font-weight:bold;" ';
$plannedStyle=' style="width:20px;text-align:center;background-color:' . $plannedBGColor . '; color: ' . $plannedFrontColor . ';" ';
$plannedStyleRed=' style="width:20px;text-align:center;background-color:' . $plannedBGColor . ';'.$styleRed.'" ';
 
echo "<table width='95%' align='center'><tr>";
echo '<td>';
echo '<table width="100%" align="left"><tr>';
echo "<td class='reportTableDataFull' style='width:20px; text-align:center;'>1</td>";
echo "<td width='100px' class='legend'>" . i18n('colRealWork') . "</td>";
echo "<td width='5px'>&nbsp;&nbsp;&nbsp;</td>";
echo '<td class="reportTableDataFull" ' . $plannedStyle . '><i>1</i></td>';
echo "<td width='100px' class='legend'>" . i18n('colPlanned') . "</td>";
echo "<td>&nbsp;</td>";
echo "<td class='legend'>" . Work::displayWorkUnit() . "</td>";
echo "<td>&nbsp;</td>";
echo "</tr></table>";
echo "<br/>";
echo '<table width="100%" align="left">';
echo '<tr rowspan="2">';
echo '<td class="reportTableHeader" rowspan="2">' . i18n('Project') . '</td>';
echo '<td class="reportTableHeader" colspan="' . count($arrRes) . '">' . i18n('Resource') . '</td>';
echo '<td class="reportTableHeader" rowspan="2" style="width:40px;">' . i18n('sum') . '</td>';
echo '</tr>';
echo '<tr>';
foreach ($arrRes as $idRes=>$name) {
  echo '<td class="reportTableLineHeader" style="width:60px;text-align:center" >'.htmlEncode($name).'</td>';
} 
echo '</tr>';
$sumProj=array();
$sumProjUnit=array();

$sortProject=array();
foreach ($arrProj as $id=>$name) {
  $sortProject[SqlList::getFieldFromId('Project', $id, 'sortOrder').'#'.$id]=$id;
}
ksort($sortProject);
$tabSorted=array();
foreach ($sortProject as $sortId=>$id) {
  $tabSorted[$id]=$arrProj[$id];
}
$arrProj=$tabSorted;

foreach ($arrProj as $idProj=>$nameProject){
  $sumProj[$idProj]=array();
  $sumProjUnit[$idProj]=array();
  // PBER #7240 : hide empty lines
  $show=false;
  foreach ($arrRes as $idRes=>$name){
    $work = (isset($tab[$idProj][$idRes]['plan']))?$tab[$idProj][$idRes]['plan']:0;
    $work += (isset($tab[$idProj][$idRes]['real']))?$tab[$idProj][$idRes]['real']:0;
    if ($work>0) {
      $show=true;
      break;
    }
  }
  if (!$show) continue;
  for ($i=1; $i<=2; $i++) {
  	if ($i==1) {
  		echo '<tr><td class="reportTableLineHeader" style="width:200px;" rowspan="2">' . htmlEncode($nameProject) . '</td>';
  		$style='';
  		$mode='real';
  		$ital=false;
  	} else {
  		echo '<tr>';
  		$style=$plannedStyle;
  		$mode='plan';
  		$ital=true;
  	}
    foreach ($arrRes as $idRes=>$name){
      if ($i==1) {
      	$sumProj[$idProj][$idRes]=0;
      	$sumProjUnit[$idProj][$idRes]=0;
      }
      echo '<td class="reportTableData" ' . $style . '>';
      echo ($ital)?'<i>':'';
      $work = (isset($tab[$idProj][$idRes][$mode]))?$tab[$idProj][$idRes][$mode]:0;
      echo Work::displayWork($work);
      echo ($ital)?'</i>':'';
      echo '</td>';
      if(isset($arrSum['resource'][$idRes])){
      	$arrSum['resource'][$idRes]+=$work;
      }else{
      	$arrSum['resource'][$idRes]=$work;
      }
      if(isset($arrSum['project'][$idProj][$mode])){
        $arrSum['project'][$idProj][$mode]+=$work;
      }else{
        $arrSum['project'][$idProj][$mode]=$work;
      }
      $sumProj[$idProj][$idRes]+=$work;
      $sumProjUnit[$idProj][$idRes]+=Work::displayWork($work);
    }
    echo '<td class="reportTableColumnHeader" style="width:50px">';
    echo ($ital)?'<i>':'';
    echo Work::displayWork($arrSum['project'][$idProj][$mode]);
    echo ($ital)?'</i>':'';
    echo '</td>';
    echo '</tr>';
  }
}
echo "<tr><td>&nbsp;</td></tr>";
echo '<tr><td class="reportTableHeader" style="width:40px;">' . i18n('sum') . '</td>';
$sum=0;
$cumul=array();
$cumulUnit=array();
foreach ($arrSum['resource'] as $idRes=>$val) {
  $sum+=$val;
  $cumul[$idRes]=$sum;
  $cumulUnit[$idRes]=Work::displayWork($sum);
  echo '<td class="reportTableHeader" >' . Work::displayWork($val) . '</td>';
}
echo '<td class="reportTableHeader">' . Work::displayWork($sum) . '</td>';
echo '</tr>';
echo '</table>';
echo '</td></tr></table>';

// Graph
if (! testGraphEnabled()) { return;}
  include_once("../external/pChart2/class/pData.class.php");
  include_once("../external/pChart2/class/pDraw.class.php");
  include_once("../external/pChart2/class/pImage.class.php");
$dataSet=new pData;
$nbItem=0;
foreach($sumProjUnit as $idProj=>$val) {
  foreach($val as $idRes=>$vals) {
    $name = SqlList::getNameFromId('Project', $idProj);
    $dataSet->setAxisPosition(0,AXIS_POSITION_LEFT);
    $dataSet->addPoints($vals,$name);
    $dataSet->setSerieDescription($name,$name);
    $dataSet->setSerieOnAxis($name,0);
    $proje=new Project($idProj);
    $projCol = $proje->color;
    $projectColor=$proje->getColor();
    $colorProj=hex2rgb($projectColor);
    if($projCol){
    	$serieSettings = array("R"=>$colorProj['R'],"G"=>$colorProj['G'],"B"=>$colorProj['B']);
    	$dataSet->setPalette($name,$serieSettings);
    } else {
    	$serieSettings = array("R"=>$rgbPalette[($nbItem % 12)]['R'],"G"=>$rgbPalette[($nbItem % 12)]['G'],"B"=>$rgbPalette[($nbItem % 12)]['B']);
    	$dataSet->setPalette($name,$serieSettings);
    }
    $nbItem++;
  }
}

if ($nbItem==0) if (!empty($cronnedScript)) goto end; else exit;

$arrLabel=array();
foreach($arrRes as $idRes=>$name){
  $arrLabel[]=$name;
}

$dataSet->addPoints($arrLabel,"resources");
$dataSet->setAbscissa("resources");

$width=1000;
$legendWidth=300;
$height=450;
$legendHeight=125;
$graph = new pImage($width+$legendWidth, $height,$dataSet);
/* Draw the background */
$graph->Antialias = FALSE;

/* Add a border to the picture */
$settings = array("R"=>240, "G"=>240, "B"=>240, "Dash"=>0, "DashR"=>0, "DashG"=>0, "DashB"=>0);
$graph->drawRoundedRectangle(5,5,$width+$legendWidth-8,$height-5,5,$settings);
$graph->drawRectangle(0,0,$width+$legendWidth-1,$height-1,array("R"=>150,"G"=>150,"B"=>150));

/* Set the default font */
$graph->setFontProperties(array("FontName"=>getFontLocation("verdana"),"FontSize"=>8));

/* title */
$graph->setFontProperties(array("FontName"=>getFontLocation("verdana"),"FontSize"=>8,"R"=>100,"G"=>100,"B"=>100));
$graph->drawLegend($width+30,17,array("Mode"=>LEGEND_VERTICAL, "Family"=>LEGEND_FAMILY_BOX ,
    "R"=>255,"G"=>255,"B"=>255,"Alpha"=>100,
    "FontR"=>55,"FontG"=>55,"FontB"=>55,
    "Margin"=>5));

/* Draw the scale */
$graph->setGraphArea(60,50,$width-20,$height-$legendHeight);
$formatGrid=array("Mode"=>SCALE_MODE_ADDALL_START0, "GridTicks"=>0,
    "DrawYLines"=>array(0), "DrawXLines"=>true,"Pos"=>SCALE_POS_LEFTRIGHT,
    "LabelRotation"=>60, "GridR"=>200,"GridG"=>200,"GridB"=>200);
$graph->drawScale($formatGrid);
$graph->Antialias = TRUE;
$graph->drawStackedBarChart(array("DisplayColor"=>DISPLAY_AUTO,"DisplaySize"=>6,"BorderR"=>255, "BorderG"=>255,"BorderB"=>255));

$serie=0;
foreach($sumProjUnit as $idProj=>$val) {
  $serie+=1;
  $name = SqlList::getNameFromId('Project', $idProj);
  $dataSet->removeSerie($name);
}

$dataSet->setAxisPosition(0,AXIS_POSITION_RIGHT);
$dataSet->addPoints($cumulUnit,"sum");
$dataSet->setSerieDescription(i18n("cumulated"),"sum");
$dataSet->setSerieOnAxis("sum",0);
$dataSet->setAxisName(0,i18n("cumulated"));

$formatGrid=array("LabelRotation"=>60,"DrawXLines"=>FALSE,"DrawYLines"=>NONE);
$graph->drawScale($formatGrid);

$graph->drawLineChart();
$graph->drawPlotChart();


$imgName=getGraphImgName("globalWorkPlanning");
$graph->Render($imgName);
echo '<table width="95%" style="margin-top:20px" align="center"><tr><td align="center">';
echo '<img src="' . $imgName . '" />'; 
echo '</td></tr></table>';
echo '<br/>';

end:

?>