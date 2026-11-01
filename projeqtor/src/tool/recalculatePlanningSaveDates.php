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

$data=RequestHandler::getValue('data');
$statAll='OK';
$lines=explode('XXX',$data);
$cpt=0; $done=0;
foreach ($lines as $dataLine) {
  $cpt++;
  $val=explode("|",$dataLine);
  if (count($val)!=4) {
    continue;
  }
  $id=$val[0];
  if (count(explode('_',$id))>1) continue;
  $start=$val[1];
  $end=$val[2];
  $updated=$val[3];
  $pe=new PlanningElement($id);
  if (!$pe->id) continue;
  $pe->quickplanStartDate=($pe->realStartDate)??$start;
  $pe->quickplanEndDate=($pe->realEndDate)??$end;
  if ($updated=='1') $pe->quickplanUpdated=1;
  $res=$pe->saveForced(true);
  $stat=getLastOperationStatus($res);
  if ($stat!='OK') {
    if ($stat!='NO_CHANGE') debugTraceLog("recalculatedPlanningSaveDates for id #$pe->id | start=$start, end=$end => $stat");
    $statAll=$stat;
  } else {
    $done++;
  }
}
echo "$cpt|$done|$statAll";
?>