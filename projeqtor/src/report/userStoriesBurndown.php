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
include_once "../tool/jsonFunctions.php";
include_once("../external/pChart2/class/pData.class.php");
include_once("../external/pChart2/class/pDraw.class.php");
include_once("../external/pChart2/class/pImage.class.php");

// ===== Parameters =====
$paramProject = '';
if (pq_array_key_exists('idProject', $_REQUEST)) {
  $paramProject = pq_trim($_REQUEST['idProject']);
  $paramProject = Security::checkValidId($paramProject);
}

$paramSprint = '';
if (pq_array_key_exists('idSprint', $_REQUEST)) {
  $paramSprint = pq_trim($_REQUEST['idSprint']);
  $paramSprint = Security::checkValidId($paramSprint);
}

// ===== Header =====
$headerParameters = "";
if ($paramProject != "") {
  $headerParameters .= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project', $paramProject)) . '<br/>';
}
if ($paramSprint != "") {
  $headerParameters .= i18n("colIdSprint") . ' : ' . htmlEncode(SqlList::getNameFromId('Sprint', $paramSprint)) . '<br/>';
}

include "header.php";

if (! testGraphEnabled()) { return; }

// idProject is mandatory
if ($paramProject == '') {
  echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  echo i18n('messageMandatory', array(i18n('colIdProject')));
  echo '</div>';
  if (!empty($cronnedScript)) goto end; else exit;
}

// ===== Determine date range =====
$startDate = '';
$endDate = '';
if ($paramSprint != '') {
  $spe = SqlElement::getSingleSqlElementFromCriteria('SprintPlanningElement', array('refType' => 'Sprint', 'refId' => $paramSprint));
  if ($spe and $spe->id) {
    if ($spe->validatedStartDate != '') $startDate = $spe->validatedStartDate;
    else if ($spe->plannedStartDate != '') $startDate = $spe->plannedStartDate;
    else if ($spe->realStartDate != '') $startDate = $spe->realStartDate;
    if ($spe->validatedEndDate != '') $endDate = $spe->validatedEndDate;
    else if ($spe->plannedEndDate != '') $endDate = $spe->plannedEndDate;
    else if ($spe->realEndDate != '') $endDate = $spe->realEndDate;
  }
} else {
  $pe = SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType' => 'Project', 'refId' => $paramProject));
  if ($pe and $pe->id) {
    if ($pe->validatedStartDate != '') $startDate = $pe->validatedStartDate;
    else if ($pe->plannedStartDate != '') $startDate = $pe->plannedStartDate;
    else if ($pe->realStartDate != '') $startDate = $pe->realStartDate;
    if ($pe->validatedEndDate != '') $endDate = $pe->validatedEndDate;
    else if ($pe->plannedEndDate != '') $endDate = $pe->plannedEndDate;
    else if ($pe->realEndDate != '') $endDate = $pe->realEndDate;
  }
}

// ===== Retrieve user stories =====
$where = getAccesRestrictionClause('UserStory', false);

// Take into account filters defined on the User Story report screen
$arrayFilter = jsonGetFilterArray('Report_UserStory', false);
if (count($arrayFilter) > 0) {
  $obj = new UserStory();
  $querySelect = "";
  $queryFrom = "";
  $queryOrderBy = "";
  $idTab = 0;
  jsonBuildWhereCriteria($querySelect, $queryFrom, $where, $queryOrderBy, $idTab, $arrayFilter, $obj);
}

$where .= " and idProject in " . getVisibleProjectsList(false, $paramProject);
if ($paramSprint != "") {
  $where .= " and idSprint=" . Sql::fmtId($paramSprint);
}

$us = new UserStory();
$lstUs = $us->getSqlElementsFromCriteria(null, false, $where, "");

$nbUs = 0;
$totalPoints = 0;
$totalValue = 0;
$minCreation = '';
$maxDone = '';
foreach ($lstUs as $u) {
  if ($u->creationDate != '') {
    $nbUs++;
    $totalPoints += (float)($u->storyPoints ?? 0);
    $totalValue  += (float)($u->businessValue ?? 0);
    if ($minCreation == '' or $u->creationDate < $minCreation) $minCreation = $u->creationDate;
    if ($u->doneDate != '' and ($maxDone == '' or $u->doneDate > $maxDone)) $maxDone = $u->doneDate;
  }
}

if ($nbUs == 0) {
  echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  echo i18n('noDataFound');
  echo '</div>';
  if (!empty($cronnedScript)) goto end; else exit;
}

// Fallback: if planning dates are missing or collapsed to a single day,
// derive the range from the user stories themselves
$today = date('Y-m-d');
if (!$startDate or !$endDate or $startDate >= $endDate) {
  if ($minCreation != '') $startDate = $minCreation;
  $endDate = ($maxDone != '' and $maxDone > $today) ? $maxDone : $today;
  if ($startDate == '' or $startDate >= $endDate) {
    // still degenerate -> widen by one day so we draw at least two points
    $startDate = addDaysToDate($endDate, -1);
  }
}

$start = date_create($startDate);
$end   = date_create($endDate);
$nbDay = $start->diff($end)->days + 1;

if ($nbDay <= 0) {
  echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  echo i18n('invalidNbOfDay');
  echo '</div>';
  if (!empty($cronnedScript)) goto end; else exit;
}

// ===== Build daily arrays (count / points / value) =====
// Ideal lines
$idealCount  = array();
$idealPoints = array();
$idealValue  = array();
for ($i = 1; $i <= $nbDay; $i++) {
  $idealCount[$i]  = ((-$nbUs)         / $nbDay) * $i + $nbUs;
  $idealPoints[$i] = ((-$totalPoints)  / $nbDay) * $i + $totalPoints;
  $idealValue[$i]  = ((-$totalValue)   / $nbDay) * $i + $totalValue;
}

// Real "left" lines - decrement as US are done
$leftCount  = array();
$leftPoints = array();
$leftValue  = array();
$remCount   = $nbUs;
$remPoints  = $totalPoints;
$remValue   = $totalValue;

// Work on a copy of doneDate so we don't mutate user stories twice
$doneDateMap = array();
foreach ($lstUs as $k => $u) {
  $doneDateMap[$k] = $u->doneDate;
}

$startTs = pq_strtotime($startDate);
for ($i = 1; $i <= $nbDay; $i++) {
  $limit = $startTs + ($i * 24 * 60 * 60);
  foreach ($lstUs as $k => $u) {
    if ($doneDateMap[$k] != '') {
      $doneTs = pq_strtotime($doneDateMap[$k]);
      if ($doneTs < $limit) {
        $remCount  -= 1;
        $remPoints -= (float)($u->storyPoints ?? 0);
        $remValue  -= (float)($u->businessValue ?? 0);
        $doneDateMap[$k] = '';
      }
    }
  }
  $leftCount[$i]  = $remCount;
  $leftPoints[$i] = $remPoints;
  $leftValue[$i]  = $remValue;
}

// ===== Build X axis labels =====
$month = getNbMonth(4, true);
$arrDays = array();
$sameMonthYear = ($month[date('n', pq_strtotime($startDate)) - 1] . '/' . date('Y', pq_strtotime($startDate)))
                == ($month[date('n', pq_strtotime($endDate)) - 1] . '/' . date('Y', pq_strtotime($endDate)));
if ($sameMonthYear) {
  for ($i = 1; $i <= $nbDay; $i++) {
    $arrDays[$i] = '';
    if ($i == 1) {
      $arrDays[1] = date('d', pq_strtotime($startDate)) . '/' . $month[date('n', pq_strtotime($startDate)) - 1] . '/' . date('Y', pq_strtotime($startDate));
    } else {
      $arrDays[$i] = date('d', pq_strtotime($startDate) + (($i - 1) * 24 * 60 * 60)) . '/' . $month[date('n', pq_strtotime($startDate) + (($i - 1) * 24 * 60 * 60)) - 1] . '/' . date('Y', pq_strtotime($startDate) + (($i) * 24 * 60 * 60));
    }
    if ($i == $nbDay) {
      $arrDays[$i] = date('d', pq_strtotime($endDate)) . '/' . $month[date('n', pq_strtotime($endDate)) - 1] . '/' . date('Y', pq_strtotime($endDate));
    }
  }
} else {
  for ($i = 1; $i <= $nbDay; $i++) {
    $arrDays[$i] = '';
    if ($i == 1) {
      $arrDays[1] = date('d', pq_strtotime($startDate)) . '/' . $month[date('n', pq_strtotime($startDate)) - 1] . '/' . date('Y', pq_strtotime($startDate));
    } else if (date('m', pq_strtotime($startDate) + ($i * 24 * 60 * 60)) == '01' and (date('d', pq_strtotime($startDate) + ($i * 24 * 60 * 60)) == '01')) {
      $arrDays[$i] = date('d', pq_strtotime($startDate) + (($i) * 24 * 60 * 60)) . '/' . $month[date('n', pq_strtotime($startDate) + (($i) * 24 * 60 * 60)) - 1] . '/' . date('Y', pq_strtotime($startDate) + (($i) * 24 * 60 * 60));
    } else if (date('d', pq_strtotime($startDate) + ($i * 24 * 60 * 60)) == '01') {
      $arrDays[$i] = date('d', pq_strtotime($startDate) + (($i) * 24 * 60 * 60)) . '/' . $month[date('n', pq_strtotime($startDate) + (($i) * 24 * 60 * 60)) - 1] . '/' . date('Y', pq_strtotime($startDate) + (($i) * 24 * 60 * 60));
    }
    if ($i == $nbDay) {
      $arrDays[$i] = date('d', pq_strtotime($endDate)) . '/' . $month[date('n', pq_strtotime($endDate)) - 1] . '/' . date('Y', pq_strtotime($endDate));
    }
  }
}

// ===== Helper to render one burndown chart =====
function renderUsBurndown($leftSerie, $idealSerie, $arrDays, $nbDay, $titleKey, $leftLabel, $idealLabel, $imgKey) {
  $dataSet = new pData();
  $dataSet->addPoints($leftSerie, "left");
  $dataSet->setSerieDescription("left", $leftLabel . "  ");
  $dataSet->setSerieOnAxis("left", 0);
  $dataSet->addPoints($idealSerie, "ideal");
  $dataSet->setSerieDescription("ideal", $idealLabel . "  ");
  $dataSet->setSerieOnAxis("ideal", 0);

  $dataSet->addPoints($arrDays, "days");
  $dataSet->setAbscissa("days");

  $dataSet->setPalette("left",  array("R" => 200, "G" => 100, "B" => 100, "Alpha" => 80));
  $dataSet->setPalette("ideal", array("R" => 100, "G" => 200, "B" => 100, "Alpha" => 80));
  $dataSet->setSerieDrawable("left", true);
  $dataSet->setSerieDrawable("ideal", true);

  $width  = 1000;
  $height = 400;
  $graph = new pImage($width, $height, $dataSet);
  $graph->Antialias = FALSE;

  $graph->setFontProperties(array("FontName" => getFontLocation("verdana"), "FontSize" => 8, "R" => 100, "G" => 100, "B" => 100));
  $graph->setGraphArea(60, 50, $width - 230, $height - 80);

  $graph->drawText($width / 2, 25, i18n($titleKey), array("FontSize" => 12, "Align" => TEXT_ALIGN_BOTTOMMIDDLE, "R" => 70, "G" => 70, "B" => 70));

  $formatGrid = array("Mode" => SCALE_MODE_START0, "GridTicks" => 0,
      "DrawYLines" => array(0), "DrawXLines" => false,
      "LabelRotation" => 60, "GridR" => 200, "GridG" => 200, "GridB" => 200);
  $graph->drawScale($formatGrid);

  $graph->drawLineChart();
  if ($nbDay < 30) {
    $graph->drawPlotChart();
  }
  $graph->drawAreaChart();

  $graph->setFontProperties(array("FontName" => getFontLocation("verdana"), "FontSize" => 8, "R" => 100, "G" => 100, "B" => 100));
  $graph->drawLegend($width - 210, 50, array("Mode" => LEGEND_VERTICAL, "Family" => LEGEND_FAMILY_BOX,
      "R" => 255, "G" => 255, "B" => 255, "Alpha" => 100,
      "FontR" => 55, "FontG" => 55, "FontB" => 55,
      "Margin" => 5));

  $imgName = getGraphImgName($imgKey);
  $graph->Render($imgName);
  echo '<table width="95%" align="center"><tr><td align="center">';
  echo '<img src="' . $imgName . '" />';
  echo '</td></tr></table>';
  echo '<br/>';
}

// ===== Render the 3 charts =====
renderUsBurndown($leftCount,  $idealCount,  $arrDays, $nbDay,
    "reportUserStoriesBurndownChart",
    i18n("userStoryLeft"),  i18n("idealNbOfUserStory"),
    "UserStories_Burndown");

renderUsBurndown($leftPoints, $idealPoints, $arrDays, $nbDay,
    "reportUserStoriesEffortBurndownChart",
    i18n("storyPointsLeft"), i18n("idealStoryPoints"),
    "UserStories_Effort_Burndown");

renderUsBurndown($leftValue,  $idealValue,  $arrDays, $nbDay,
    "reportUserStoriesValueBurndownChart",
    i18n("businessValueLeft"), i18n("idealBusinessValue"),
    "UserStories_Value_Burndown");

end:
?>
