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

/*
 * ============================================================================
 * Habilitation defines right to the application for a menu and a profile.
 */
require_once "../tool/projeqtor.php";
require_once "../tool/kanbanFunction.php";

$columnType = RequestHandler::getValue('columnType');
$idColumn = RequestHandler::getValue('idColumn');
$idKanban = RequestHandler::getId('idKanban');
$isStatus = ($columnType == 'Status')?true:false;
$kanban = new Kanban ( $idKanban, true );
$json = json_decode ( $kanban->param, true );
$typeData = $json ['typeData'];

$listForbiden = array ();
$kanbanColumnName = array();
$columnRanges=array();
$idColumnByColumn = array();
if (isset ( $json ['column'] )){
	foreach ( $json ['column'] as $idx=>$line ) {
	  if($line['from']=="n")$line['from']='0';
		$listForbiden [] = $line ['from'];
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
		  $columnRanges[$idCol] = array('from' => $idCol, 'to' => $idCol);
		}
	}
}

if ($isStatus) {
  $workflowStatus = new WorkflowStatus();
  $tableName2 = $workflowStatus->getDatabaseTableName();
  $typeObj = new Type();
  $tableName3 = $typeObj->getDatabaseTableName();
  $statusObj = new Status();
  $tableName = $statusObj->getDatabaseTableName();
  
  // Récupérer tous les statuts du workflow dans l'ordre
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
  
  // Construire la liste des statuts à récupérer pour chaque colonne
  foreach($columnRanges as $colId => $range){
    // Trouver tous les statuts entre from et to
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
      // Dernière colonne - tous les statuts depuis from jusqu'à la fin
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

if ($isStatus) {
	$status = new Status ();
	$tableName = $status->getDatabaseTableName ();
	$workflowStatus = new WorkflowStatus ();
	$tableName2 = $workflowStatus->getDatabaseTableName ();
	$type = new Type ();
	$tableName3 = $type->getDatabaseTableName ();
	$result = Sql::query ( "SELECT s.id as id, s.name as name from $tableName s where s.idle=0 and (s.id in (select idStatusFrom from $tableName2 w, $tableName3 t where t.idWorkflow=w.idWorkflow and t.scope='$typeData')
    or s.id in (select idStatusTo from $tableName2 w, $tableName3 t where t.idWorkflow=w.idWorkflow and t.scope='$typeData') ) order by s.sortOrder" );
	$listToHave = array ();
	while ( $line = Sql::fetchLine ( $result ) ) {
		$listToHave [$line ['id']] = $line ['name'];
	}
} else {
	$crit = array (
			'idle' => '0' 
	);
	$selectedProject=Project::getSelectedProject();
	if ($columnType != 'Project' and property_exists ( $columnType, 'idProject' ) 
	and $selectedProject and $selectedProject!= '*' and pq_strpos($selectedProject,',')===false) {
		$crit ['idProject'] = $selectedProject;
	}
	if ($columnType=='Activity' and $typeData=='Ticket') { // This if we want restriction whatever the restriction parameter : we'll list only Actual Planning Activities
	  $crit['isPlanningActivity']='1';
	}
	$listToHave=array();
	if ($columnType == 'Milestone') {
	  $where = 'idle = 0 and idProject in '.getVisibleProjectsList();
	  $milestone = new Milestone();
	  $milestoneList = $milestone->getSqlElementsFromCriteria(null,null,$where);
	  foreach ($milestoneList as $ms){
	    $listToHave[$ms->id] = $ms->name;
	  }
	}else{
	  $listToHave = SqlList::getListWithCrit ( $columnType, $crit );
	}
	if ($columnType == 'TargetProductVersion') {
		$restrictArray = getSessionUser ()->getVisibleVersions ();
		$listToHave = array_intersect_key ( $listToHave, $restrictArray );
	}
}
$listFinal = array ();
foreach ( $listToHave as $elmId => $elmName ) {
	$find = false;
	for($iterateur = 0; $iterateur < count ( $listForbiden ) && ! $find; $iterateur ++) {
		$find = $listForbiden [$iterateur] == $elmId;
	}
	if (! $find and $elmId !=0) {
		$listFinal [$elmId] = $elmName;
	}
}

$titleSourceColumn = '';
switch ($columnType){
  case 'Status':
    $titleSourceColumn = ucfirst(i18n('statusForFilter'));
    break;
  case 'Activity':
    $titleSourceColumn = ucfirst(i18n('colPlanningActivity'));
    break;
  case 'Milestone':
    $titleSourceColumn = ucfirst(i18n('moduleTargetMilestone'));
    break;
  case 'TargetProductVersion':
    $titleSourceColumn = ucfirst(i18n('colIdTargetProductVersion'));
    break;
}

?>
<form id='columnManagmentForm' name='columnManagmentForm' onSubmit="return false;" style="overflow:hidden;text-align:center">
  <input type="hidden" id="jsonColumn" name="jsonColumn" value="" />
  <input type="hidden" id="columnType" name="columnType" value="<?php echo $columnType; ?>" />
  <input type="hidden" id="idColumn" name="idColumn" value="<?php echo $idColumn; ?>" />
  <input type="hidden" id="idKanban" name="idKanban" value="<?php echo $idKanban; ?>" />
  <input type="hidden" id="typeData" name="typeData" value="<?php echo $typeData; ?>" />
  <table style="width: 100%;">
  <?php if($idColumn == ''){?>
    <tr>
    	<td>
    		<div style="text-align:left;font-weight:normal;width:150px;text-align:center;" class="tabLabel longTextLabel"><?php echo $titleSourceColumn;?></div>
    		<div dojotype="dojo.dnd.Source" id="columnManagmentDndSource" jsId="columnManagmentDndSource" dndType="columnManagmentSource" data-dojo-props="accept: ['columnManagmentItem'], horizontal: true, singular:true"
    			class="columnManagmentSource" withHandles="true">
    			<?php $countItem = 2;
    			foreach ($listFinal as $elmId => $elmName){
    			  $sortOrder = (isset($columnSortOrders[$elmId]))?$columnSortOrders[$elmId]:$countItem;
    			  $bgColor = ($isStatus)?SqlList::getFieldFromId('Status', $elmId, 'color'):'var(--color-light)';
    			  $color = htmlForeColorForBackgroundColor($bgColor);
  			  ?>	
    				<div id="itemSource<?php echo $elmId;?>" from="<?php echo $elmId;?>" namecolumn="<?php echo $elmName;?>" sortorder="<?php echo $sortOrder;?>" class="dojoDndItem columnManagmentItem itemSource" dndtype="columnManagmentItem" style="position: relative;background-color:<?php echo $bgColor; ?>;color:<?php echo $color;?>;border-radius:17px;padding: 0px;">
    					<div class="columnItem" style="padding:8px;">
    					<table style="width:100%;height:100%">
  								<tr class="itemColumnHeaderTR" style="display:none;">
  									<td class="itemColumnHeader">
          						<div class="itemColumnName" style="display:flex;align-items:center;">
          							<div class="itemColumnOrder" style="font-weight:bold;margin-right:5px;" >N°<?php echo $countItem;?></div>
          							<input id="nameColumn_<?php echo $elmId;?>" style="width:151px;" class="dijitLikeTextBox input required" type="text" name="nameColumn_<?php echo $elmId;?>" value="<?php echo htmlEncode($elmName);?>"/>
          						</div>
        						</td>
      						</tr>
        					<tr class="dojoDndHandle" style="cursor:move;">
        						<td class="itemColumnContent" style="height:100%;cursor:move;">
        							<div class="itemColumnContentTarget" style="display: none;align-items: center;justify-content: center;">
        								<div class="cmStatusWrap">
            						<?php
            						if($isStatus){
            						    echo '<div class="cmStatusItem">'.formatColorRounded ($bgColor, 15  , 8, 'left', $elmName, $elmName, 7).'</div>';
            						}else{
            						  echo ucfirst($elmName);
            						}
            						?>
          							</div>
          						</div>
        							<div class="itemColumnContentSource" style="display: flex;align-items: center;justify-content: center;height:18px">
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
    	</td>
    </tr>
    <tr>
    	<td style="position: relative;">
    		<div align="center" style="position: absolute;width: 100%;top: 10px;" ><div id="kanbanColumnDndHelper" style="width: 32px;height: 32px;"><?php echo formatIcon('ArrowDown', 32);?></div></div>
    		<div dojoType="dijit.Tooltip" connectId="kanbanColumnDndHelper" position="below">
        <?php echo i18n('kanbanColumnDndHelper');?>
        </div>
    		<br/>
  		</td>
		</tr>
    <tr>
    	<td>
    		<div id="columnManagementTargetDiv" dojoType="dijit.layout.ContentPane" region="top">
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
          							<input id="nameColumn_<?php echo $elmId;?>" style="width:151px;" class="dijitLikeTextBox input required" type="text" name="nameColumn_<?php echo $elmId;?>" value="<?php echo htmlEncode($elmName);?>" onchange="updateColumnName();" />
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
            						    foreach ($idColumnByColumn[$elmId] as $idStatus){
            						      $color = SqlList::getFieldFromId('Status', $idStatus, 'color');
            						      echo '<div class="cmStatusItem" title="'.$statusTitle.'">'.formatColorRounded ($color, 15  , 8, 'left', $statusTitle, SqlList::getNameFromId($columnType, $idStatus), 7).'</div>';
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
    	</td>
    </tr>
    <?php }else{?>
    <tr>
    	<td>
    		<?php 
    		$elmId = $idColumn;
    		$elmName = $kanbanColumnName[$idColumn];
    		$countItem = array_search($idColumn, array_keys($kanbanColumnName))+1;
    		$sortOrder = (isset($columnSortOrders[$elmId]))?$columnSortOrders[$elmId]:$countItem;
    		$dndClass = " dojoDndItem";
    		$dndType = 'dndtype="columnManagmentItem"';
    		$dndHandle = "dojoDndHandle";
    		$cursor = "cursor:unset;";
    		$bgColor = ($isStatus)?SqlList::getFieldFromId('Status', $elmId, 'color'):'var(--color-light)';
    		$color = htmlForeColorForBackgroundColor($bgColor);
    	  ?>
    		<div id="itemTarget<?php echo $elmId;?>" from="<?php echo $elmId;?>" namecolumn="<?php echo $elmName;?>" sortorder="<?php echo $sortOrder;?>" class="columnManagmentItem itemTarget<?php echo $dndClass;?>" <?php echo $dndType;?> style="position: relative;background-color:<?php echo $bgColor; ?>;color:<?php echo $color;?>;border-radius:17px;padding: 0px;">
  				<div class="columnItem" style="padding:8px;">
  					<table style="width:100%;height:100%">
  						<tr class="itemColumnHeaderTR">
  							<td class="itemColumnHeader">
  								<div class="itemColumnName" style="display:flex;align-items:center;">
      							<div class="itemColumnOrder" style="font-weight:bold;margin-right:5px;" >N°<?php echo $countItem;?></div>
      							<input id="nameColumn_<?php echo $elmId;?>" style="width:151px;" class="dijitLikeTextBox input required" type="text" name="nameColumn" value="<?php echo htmlEncode($elmName);?>" />
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
        						    foreach ($idColumnByColumn[$elmId] as $idStatus){
        						      $nameStatus = SqlList::getNameFromId($columnType, $idStatus);
        						      $hideStatusTitle = i18n('columnManagmentHideStatus', array($nameStatus));
        						      $statusTitle = SqlList::getNameFromId($columnType, $idStatus);
        						      $color = SqlList::getFieldFromId('Status', $idStatus, 'color');
        						      $isHidedStatus = Parameter::getUserParameter('kanbanColumnStatusHide_'.$idKanban.'_'.$idStatus);
        						      $isHidedStatus = ($isHidedStatus == '1')?true:false;
        						      $hide = ($isHidedStatus)?'0':'1';
        						      echo '<div class="cmStatusItem">';
        						      echo '  <input type="hidden" id="isColumnStatusHided_'.$idStatus.'" name="isColumnStatusHided_'.$idStatus.'" value="'.$hide.'" />';
        						      echo '  <div id="columnHideStatus_'.$idStatus.'" style="margin:5px" title="'.$hideStatusTitle.'" onclick="kanbanColumnHideStatus('.$idKanban.','.$idStatus.');">'.formatSmallButton(($isHidedStatus)?'View':'NoView').'</div>';
        						      echo '  <div id="columnStatus_'.$idStatus.'" style="'.(($isHidedStatus)?'opacity:0.25;':'').'">'.formatColorRounded ($color, 15  , 8, 'left', $statusTitle, $nameStatus, 7).'</div>';
        						      echo '</div>';
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
    	</td>
    </tr>
     <?php }?>
    <tr><td><br/></td></tr>
    <tr>
  		<td align="center">
  			<button class="mediumTextButton" dojoType="dijit.form.Button" type="button"
  				onclick="dijit.byId('dialogKanbanManageColumn').hide();formChangeInProgress=false;">
          <?php echo i18n("buttonCancel");?>
        </button>
  			<button class="mediumTextButton" id="dialogKanbanUpdateSubmit" dojoType="dijit.form.Button" type="submit"
  				onclick="protectDblClick(this);saveKanbanColumnManagment(<?php echo ($idColumn != '')?true:false; ?>);return false;">
          <?php echo i18n("buttonOK");?>
        </button>
     </td>
  	</tr>
  </table>
</form>