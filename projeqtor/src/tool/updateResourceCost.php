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

$idRole = RequestHandler::getId('idRole');
$updateResourceCostOption = RequestHandler::getValue('updateResourceCostOption');
$updateResourceCostStartDate = RequestHandler::getValue('updateResourceCostStartDate');

$role = new Role($idRole);

$resourceCost = new ResourceCost();
$resourceCostList = $resourceCost->getSqlElementsFromCriteria(array('idRole'=>$idRole, 'idle'=>'0', 'endDate'=>null));

$resultArray = array();

Sql::beginTransaction();

foreach ($resourceCostList as $resourceCost){
  $isSubContractor = SqlList::getFieldFromId('Resource', $resourceCost->idResource, 'subcontractor');
  if ($isSubContractor and $role->defaultExternalCost==0) continue;
  if (! $isSubContractor and $role->defaultCost==0) continue;
  if($updateResourceCostOption == 'updateOptionCostFromDate'){
    $rc = new ResourceCost();
    $rc->idResource=$resourceCost->idResource;
    $rc->idRole=$idRole;
    $rc->cost=($isSubContractor)?$role->defaultExternalCost:$role->defaultCost;
    $rc->startDate=$updateResourceCostStartDate;
    $resultArray[]=$rc->save();
  }else if($updateResourceCostOption == 'updateOptionReplaceActualCost'){
    if(!$resourceCost->endDate){
      $resourceCost->startDate = '';
      $resourceCost->cost=($isSubContractor)?$role->defaultExternalCost:$role->defaultCost;
      $resultArray[]=$resourceCost->save();
    }
  }else if($updateResourceCostOption == 'updateOptionFullReplaceCost'){
    if(!$resourceCost->endDate){
      $resourceCost->startDate = '';
      $resourceCost->cost=($isSubContractor)?$role->defaultExternalCost:$role->defaultCost;
      $resultArray[]=$resourceCost->save();
      $ass=new Assignment();
      $assList=$ass->getSqlElementsFromCriteria(array('idRole'=>$idRole, 'idResource'=>$resourceCost->idResource));
      foreach ($assList as $ass){
        $ass->dailyCost = ($isSubContractor)?$role->defaultExternalCost:$role->defaultCost;
        $resultArray[]=$ass->save();
      }
    }
  }
}

if (isset($resultArray)) {
  $KOArray = array();
  $KOmsg='OK';
  foreach ($resultArray as $result){
    $status=getLastOperationStatus($result);
    $msg=getLastOperationMessage($result);
    if ($status!='OK' and $status!='NO_CHANGE') {
      if ($status=='ERROR') {
        $KOmsg='ERROR';
      } if ($status=='INVALID' and $KOmsg!='ERROR') {
        $KOmsg='INVALID';
      } else {
        $KOmsg=$status;
      }
      $KOArray[]='<div>'.pq_substr($result,pq_strpos($result,'<br/><br/>')).'</div>';
    }
  }
  sql::commitTransaction();
  if(count($KOArray)>0){
    echo '<div class="message'.$KOmsg.'" >';
    foreach ($KOArray as $KO){
      echo $KO;
      echo '<br/>';
    }
    echo '</div>';
  }else{
    echo '<div class="messageOK" >'.i18n('dialogUpdateResourceCost').' '.i18n("done").'</div>';
    echo '<input type="hidden" id="lastOperation" name="lastOperation" value="save">';
    echo '<input type="hidden" id="lastOperationStatus" name="lastOperationStatus" value="OK">';
  }
}
?>