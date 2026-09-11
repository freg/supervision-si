<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 ******************************************************************************
 *** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
 ******************************************************************************
 *
 * Copyright 2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 *
 * This file is an add-on to ProjeQtOr, packaged as a plug-in module.
 * It is NOT distributed under an open source license.
 * It is distributed in a proprietary mode, only to the customer who bought
 * corresponding licence.
 * The company ProjeQtOr remains owner of all add-ons it delivers.
 * Any change to an add-ons without the explicit agreement of the company
 * ProjeQtOr is prohibited.
 * The diffusion (or any kind if distribution) of an add-on is prohibited.
 * Violators will be prosecuted.
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";

$columnType = RequestHandler::getValue('columnType');
$idColumn = RequestHandler::getValue('idColumn');
$jsonColumn = RequestHandler::getValue('jsonColumn');
$json = json_decode ($jsonColumn, true);
$typeData = $json ['typeData'];
$isStatus = ($columnType == 'Status')?true:false;

$kanbanColumnName = array();
$columnRanges=array();
$idColumnByColumn = array();
if (isset ( $json ['column'] )){
  foreach ( $json ['column'] as $idx=>$line ) {
    if($line['from']=="n")$line['from']='0';
    $kanbanColumnName[$line['from']] = $line['name'];
    $nextFrom = null;
    $idCol = ($line['from'] == 'n')?'0':$line['from'];
    if($columnType == 'Status' and $idCol != '0'){
      for($j = $idx + 1; $j < count($json['column']); $j++){
        $nextCol = $json['column'][$j];
        $nextIdCol = ($nextCol['from'] == 'n')?'0':$nextCol['from'];
        if($nextIdCol != '0'){
          $nextFrom = $nextIdCol;
          break;
        }
      }
      $columnRanges[$idCol] = array('from' => $idCol, 'to' => $nextFrom);
    }else{
      $columnRanges[$idCol] = array('from' => $idCol, 'to' => $idCol);;
    }
  }
}

if ($columnType == 'Status') {
  $workflowStatus = new WorkflowStatus();
  $tableName2 = $workflowStatus->getDatabaseTableName();
  $typeObj = new Type();
  $tableName3 = $typeObj->getDatabaseTableName();
  $statusObj = new Status();
  $tableName = $statusObj->getDatabaseTableName();
  
  $queryAllStatus = "SELECT s.id, s.sortOrder as sortorder
                     FROM $tableName s
                     WHERE s.idle=0
                     AND (s.id IN (SELECT idStatusFrom FROM $tableName2 w, $tableName3 t
                                   WHERE t.idWorkflow=w.idWorkflow AND t.scope='$typeData')
                          OR s.id IN (SELECT idStatusTo FROM $tableName2 w, $tableName3 t
                                      WHERE t.idWorkflow=w.idWorkflow AND t.scope='$typeData'))
                     ORDER BY s.sortOrder";
  $resultAllStatus = Sql::query($queryAllStatus);
  $allStatusInOrder = array();
  $columnSortOrders = array();
  while($lineStatus = Sql::fetchLine($resultAllStatus)){
    $allStatusInOrder[] = $lineStatus['id'];
    if(!isset($columnSortOrders[$lineStatus['id']])){
      $columnSortOrders[$lineStatus['id']]=$lineStatus['sortorder'];
    }
  }
  foreach($columnRanges as $colId => $range){
    $fromIdx = array_search($range['from'], $allStatusInOrder);
    if($range['to'] !== null){
      $toIdx = array_search($range['to'], $allStatusInOrder);
      if($fromIdx !== false && $toIdx !== false){
        for($i = $fromIdx; $i < $toIdx; $i++){
          if(!isset($idColumnByColumn[$colId])){
            $idColumnByColumn[$colId]=array();
          }
          $idColumnByColumn[$colId][]=$allStatusInOrder[$i];
        }
      }
    }else{
      if($fromIdx !== false){
        for($i = $fromIdx; $i < count($allStatusInOrder); $i++){
          if(!isset($idColumnByColumn[$colId])){
            $idColumnByColumn[$colId]=array();
          }
          $idColumnByColumn[$colId][]=$allStatusInOrder[$i];
        }
      }
    }
  }
  foreach ($idColumnByColumn as $idCol=>$statusCol){
    $columnRanges[$idCol] = array('from' => $idCol, 'to' => $statusCol[array_key_last($statusCol)]);
  }
}else{
  foreach($columnRanges as $colId => $range){
    if(!isset($idColumnByColumn[$colId])){
      $idColumnByColumn[$colId]=array();
    }
    $idColumnByColumn[$colId][]=$range['from'];
  }
}
?>
<div style="text-align:left;font-weight:normal;width:150px;text-align:center;" class="tabLabel longTextLabel"><?php echo i18n('backlogStatusSelected');?></div>
  <div dojoType="dojo.dnd.Source" id="columnManagmentDndTarget" jsId="columnManagmentDndTarget" dndType="columnManagmentTarget" data-dojo-props="accept: ['columnManagmentItem'], horizontal: true, singular:true, copyOnly:true, selfAccept:false"
  	class="columnManagmentTarget" withHandles="true">
  	<?php $countItem = 1;
  	foreach ($kanbanColumnName as $elmId => $elmName){
  	  $sortOrder = (isset($columnSortOrders[$elmId]))?$columnSortOrders[$elmId]:$countItem;
  	  $isBacklog = ($countItem == 1)?true:false;
      $dndClass = " dojoDndItem";
      $dndType = 'dndtype="columnManagmentItem"';
      $dndHandle = "dojoDndHandle";
      $cursor = "cursor:move;";
      $bgColor = ($isStatus)?SqlList::getFieldFromId('Status', $elmId, 'color'):'var(--color-light)';
      $color = htmlForeColorForBackgroundColor($bgColor);
      if($isBacklog){
        $dndClass = "";
        $dndType = "";
        $dndHandle = "";
        $cursor = "cursor:unset !important;";
      }
    ?>
  	<div id="itemTarget<?php echo $elmId;?>" from="<?php echo $elmId;?>" namecolumn="<?php echo $elmName;?>" sortorder="<?php echo $sortOrder;?>" class="columnManagmentItem <?php echo ($isBacklog)?'backlogColumn':'';?> itemTarget<?php echo $dndClass;?>" <?php echo $dndType;?> style="position: relative;background-color:<?php echo $bgColor; ?>;color:<?php echo $color;?>;border-radius:17px;padding: 0px;">
  		<div class="columnItem" style="padding:8px;">
  			<table style="width:100%;height:100%">
  				<tr class="itemColumnHeaderTR">
  					<td class="itemColumnHeader">
  						<div class="itemColumnName" style="display:flex;align-items:center;">
  							<div class="itemColumnOrder" style="font-weight:bold;margin-right:5px;" >N°<?php echo $countItem;?></div>
  							<input id="nameColumn_<?php echo $elmId;?>" style="width:151px;" class="dijitLikeTextBox input required" type="text" name="nameColumn_<?php echo $elmId;?>" value="<?php echo htmlEncode($elmName);?>"  onchange="updateColumnName();"/>
  						</div>
  					</td>
  				</tr>
  				<tr class="<?php echo $dndHandle;?>" style="<?php echo $cursor;?>">
  					<td class="itemColumnContent" style="<?php echo $cursor;?>">
  						<div class="itemColumnContentTarget" style="display: flex;align-items: center;justify-content: center;">
    						<div class="cmStatusWrap">
    						<?php
    						if($isStatus){
    						  if(isset($idColumnByColumn[$elmId])){
    						    $statusTitle = i18n('from').' '.SqlList::getNameFromId($columnType, $idColumnByColumn[$elmId][array_key_first($idColumnByColumn[$elmId])]).' '.i18n("to").' '.SqlList::getNameFromId($columnType, $idColumnByColumn[$elmId][array_key_last($idColumnByColumn[$elmId])]);
    						    foreach ($idColumnByColumn[$elmId] as $idColumn){
    						      $color = SqlList::getFieldFromId('Status', $idColumn, 'color');
    						      echo '<div class="cmStatusItem" title="'.$statusTitle.'">'.formatColorRounded ($color, 15  , 8, 'left', $statusTitle, SqlList::getNameFromId($columnType, $idColumn), 7).'</div>';
    						    }
    						  }
    						}else{
    						  echo ucfirst($elmName);
    						}
    						?>
  							</div>
  						</div>
  						<div class="itemColumnContentSource" style="display: none;align-items: center;justify-content: center;height:18px">
  							<span class="itemColumnText"><?php echo ucfirst($elmName);?></span>
  						</div>
  					</td>
  				</tr>
  			</table>
  		</div>
  	</div>
  	<?php $countItem++;
   }?>
  </div>
</div>