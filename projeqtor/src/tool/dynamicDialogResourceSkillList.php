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

/* ============================================================================
 * Presents the list of objects of a given class.
 *
 */
require_once "../tool/projeqtor.php";
include_once('../tool/formatter.php');
scriptLog('   ->/view/dynamicDialogResourceSkillList.php');

$ratioPertinence = 0.75;
$result = '';

$idActivity=RequestHandler::getId('idActivity');
$critFld=RequestHandler::getValue('critFld');
$critVal=RequestHandler::getValue('critVal');

$obj = new Activity($idActivity);

$activitySkill = new ActivitySkill();
$activitySkillList = $activitySkill->getSqlElementsFromCriteria(array('idActivity'=>$idActivity));

//======================================================
$prj=new Project($critVal, true);
$lstTopPrj=$prj->getTopProjectList(true);
$in=transformValueListIntoInClause($lstTopPrj);
$today=date('Y-m-d');
$where="idProject in " . $in;
$where.=" and idle=0";
$where.=" and (endDate is null or endDate>='$today')";
$aff=new Affectation();
$list=$aff->getSqlElementsFromCriteria(null,null, $where);
$nbRows=0;
$resourceList=array();
$planningMode = null;
if($obj and property_exists($obj, get_class($obj).'PlanningElement')){
	$peFld=get_class($obj)."PlanningElement";
	$pMode = new PlanningMode($obj->$peFld->idPlanningMode);
	$planningMode = $pMode->code;
}
foreach ($list as $aff) {
	if (! pq_array_key_exists($aff->idResource, $resourceList)) {
		$id=$aff->idResource;
		$isResourceTeam=SqlList::getFieldFromId('ResourceAll', $id, 'isResourceTeam');
		//if($planningMode == 'MAN' and $isResourceTeam)continue;
		if($isResourceTeam)continue;
		$name=SqlList::getNameFromId('ResourceAll', $id);
		if ($name!=$id) {
			$resourceList[$id]=$name;
		}
	}
}
asort($resourceList);
$idResourceList = array_flip($resourceList);
foreach ($idResourceList as $idResource){
  $resultRow[$idResource] = '';
}

//======================================================
$querySelect = " * ";
$resourceSkill = new ResourceSkill();
$queryFrom = $resourceSkill->getDatabaseTableName();
$queryWhere='idle=0';
$recSkillList = array();
$listSkill = array();
$listActSkill=array();
foreach ($activitySkillList as $activitySkill){
  $listSkill[] = $activitySkill->idSkill;
  $listActSkill[$activitySkill->idSkill]=$activitySkill->idSkillLevel;
}
$flatSubList = implode(',', $listSkill);
$queryWhere .= " and idSkill in (0,".$flatSubList.")";
$queryWhere .= " and idResource in (".implode(',', $idResourceList).")";
$queryOrderBy = "id";
// constitute query and execute
$query='select ' . $querySelect
. ' from ' . $queryFrom
.' where ' . $queryWhere
. ' order by ' . $queryOrderBy;
$result=Sql::query($query);
?>

<table style="width:700px">
<tr><td colspan=2 style="width:100%;"><table style="width:100%;">
<tr>
<td class="assignHeader" style="width:30%;"><?php echo i18n('colIdResource');?></td>
<td class="assignHeader" style="width:55%" colspan="2" ><?php echo i18n('colIdSkill');?></td>
<td class="assignHeader" style="width:15%" colspan="2"><?php echo i18n('colPertinence');?></td>
</tr>
<?php 
$rowLine = array();
$storeRow = array();
$resultLine = '';
if (1 or Sql::$lastQueryNbRows > 0) {
	while ($line = Sql::fetchLine($result)) {
		$line=array_change_key_case($line,CASE_LOWER);
		$recSkillList[$line['idresource']][$line['idskill']]=$line;
	}
    foreach ($resultRow as $idResource=>$row){
      foreach ($listSkill as $idSkill){
      	if(!isset($recSkillList[$idResource][$idSkill]))$recSkillList[$idResource][$idSkill]=array(0=>0);
      }
      if(!isset($recSkillList[$idResource])){
        $list = array(0=>0);
      }else{
        $list = $recSkillList[$idResource];
      }
      showSkill($idResource, $list, $listActSkill, $resultRow);
    }
    foreach ($resultRow as $idResource=>$row){
    	$pertinance = pq_substr($row, pq_strpos($row, '[p1]')+4, (pq_strpos($row, '[p2]')-pq_strpos($row, '[p1]')-4));
  		$rowLine[$idResource]=$pertinance;
    }
    arsort($rowLine);
    foreach ($rowLine as $idResource=>$replace){
      $row = $resultRow[$idResource];
      $search = pq_substr($row, pq_strpos($row, '[p1]'), (pq_strpos($row, '[p2]')-pq_strpos($row, '[p1]')+4));
      $displayRow = pq_str_replace($search, $replace, $row);
      echo $displayRow;
    }
}
?>
<tr><td><br/></td></tr>
<tr>
  <td align="center" colspan="5">
    <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogResourceSkillList').hide();">
      <?php echo i18n("buttonCancel");?>
    </button>
  </td>
</tr>
</table>
<?php
function showSkill($idResource, $skillList, $listActSkill, &$resultRow) {
	$result = '';
	$firstRow = true;
	$lastRow = false;
	$sortBy=array();

	$skillLevel = new SkillLevel();
	$minWeight = $skillLevel->getMinValueFromCriteria('weight', null, "1=1");
	
	foreach ($skillList as $idSkill=>$skill){
        $isSkill = (!isset($skill['id']))?false:true;
        if($idSkill == 0){
          $sortBy[$idResource]=0;
          continue;
        }
        $txPerti = 0;
        if($isSkill){
          $weight = 1;
          $pertinence = 1;
          $skillLevel = new SkillLevel($skill['idskilllevel']);
          $weight = $skillLevel->weight;
          if(isset($listActSkill[$idSkill])){
          	$skillMaxLevel = new SkillLevel($listActSkill[$idSkill]);
          	$maxWeight = $skillMaxLevel->weight;
          }else{
          	$maxWeight = $skillLevel->getMaxValueFromCriteria('weight', array('id'=>$skillLevel->id), null);
          }
          $txWeight=($weight/$maxWeight > 1)?1:($weight/$maxWeight);
          $txPerti = $pertinence*$txWeight;
        }
		if(!isset($sortBy[$idResource])){
          $sortBy[$idResource]=$txPerti;
        }else{
          $sortBy[$idResource]+=$txPerti;
        }
	}
    
	$idRow = 'id="resourceSkillRow'.$idResource.'"';
	$result .='<TR class="resourceSkillRow" '.$idRow.' style="height:40px !important;" onclick=selectResourceFromSkill('.$idResource.');"">';
	$resourceName = SqlList::getNameFromId('Resource', $idResource);
	$resourceId = $idResource;
	$result .='  <TD class="resourceSkillTableData">';
	if($firstRow){
		$result .='<TABLE style="width:100%;height:100%"><TR>';
		$result .='<TD align="left" style="width:20%;padding-left:5px;padding-right:5px;">'.formatUserThumb($resourceId, $resourceName, $resourceName).'</TD>';
		$result .='<TD align="left" style="width:80%;">'.$resourceName.'</TD>';
		$result .='</TR></TABLE>';
	}
	$result .='  </TD>';
	$result .=' <TD  class="resourceSkillTableData" colspan="2" ><TABLE style="width:100%;height:100%">';
	foreach ($skillList as $idSkill=>$skill){
        $isSkill = (!isset($skill['id']))?false:true;
        if($isSkill){
          $idRow = 'id="skillRow_'.$idResource.'_'.$idSkill.'"';
          $result .=' <TR>';
          $resourceName = SqlList::getNameFromId('Resource', $idResource);
          $resourceId = $idResource;
          $skillLevel = new SkillLevel();
          if($idSkill != 0){
          	$skillLevel = new SkillLevel($skill['idskilllevel']);
          }
          $result .='  <TD align="center" style="width:50%;" title="'.$skillLevel->name.'"><img src="icons/'.$skillLevel->icon.'" alt="'.$skillLevel->name.'" style="height: 36px;"></TD>';
          $name = ($idSkill != 0)?SqlList::getNameFromId('Skill', $skill['idskill']):'';
          $result .='  <TD style="width:50%;text-align:left;">'.htmlEncode($name).'</TD>';
          $result .='  </TR>';
          $firstRow=false;
        }
    }
    $result .=' </TABLE></TD>';
    $txPerti = $sortBy[$idResource]/count($skillList);
    $txGlobal = round($txPerti*100);
    $color="";
    if($txGlobal == 0)$color="background-color:#ebebeb";
    if($txGlobal > 0 and $txGlobal <=50)$color="background-color:orange";
    if($txGlobal > 50 and $txGlobal <=75)$color="background-color:gold";
    if($txGlobal > 75 and $txGlobal <=100)$color="background-color:#45d545";
    $result .='  <TD class="ganttName resourceSkillTableData" style="'.$color.'">[p1]' . $txGlobal . '[p2]%</TD>';
    $result .=' </TR>';
    $resultRow[$idResource] = $result;
}
?>
