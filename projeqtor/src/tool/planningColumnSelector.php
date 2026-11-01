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

/** ===========================================================================
 * Display the column selector div
 */

require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/planningColumnSelector');

$columns=Parameter::getPlanningColumnOrder($planningType);
$columnsAll=Parameter::getPlanningColumnOrder($planningType,true);
$desc=Parameter::getPlanningColumnDescription($planningType);

if($planningType == 'portfolio'){
  $project = new Project();
  $hiddenProjectField = $project->getExtraHiddenFields('*', null, getSessionUser()->getProfile(), true);
  foreach ($columnsAll as $order=>$col) {
    $field = pq_strtolower(pq_substr($col, 0, 1)).pq_substr($col, 1);
    if($col == 'IdHealthStatus')$field='idHealth';
    if($col == 'QualityLevel')$field='idQuality';
    if($project->isAttributeSetToField($field, 'hidden')){
      if(!in_array($field, $hiddenProjectField))$hiddenProjectField[]=$field;
    }
  }
  if(in_array('idHealth', $hiddenProjectField))$hiddenProjectField[array_search('idHealth', $hiddenProjectField)]='idHealthStatus';
  if(in_array('idQuality', $hiddenProjectField))$hiddenProjectField[array_search('idQuality', $hiddenProjectField)]='qualityLevel';
}

if($planningType == 'planning'){
  $activity = new Activity();
  $hiddenActivityField = $activity->getExtraHiddenFields('*', null, getSessionUser()->getProfile(), true);
  foreach ($columnsAll as $order=>$col) {
    $field = pq_strtolower(pq_substr($col, 0, 1)).pq_substr($col, 1);
    if($activity->isAttributeSetToField($field, 'hidden')){
      if(!in_array($field, $hiddenActivityField))$hiddenActivityField[]=$field;
    }
  }
}

foreach ($columnsAll as $order=>$col) {
    if ( (isset($resourcePlanning) and ($col=='ValidatedWork' or $col=='Resource' or pq_substr($col,-4)=='Cost') )
        or (isset($portfolioPlanning) and ($col=='Resource' or $col=='IdPlanningMode' or $col=='RespInitial' or $col=='IdResource') )
        or (isset($versionPlanning) and (pq_substr($col,-4)=='Cost' or $col=='Responsible' or $col=='RespInitial' or $col=='ValidatedStartDate' or $col=='ValidatedEndDate'))
        or (isset($contractGantt) and ($col=='Responsible' or $col=='RespInitial' or $col=='ValidatedStartDate' or $col=='ValidatedEndDate'))) {
        // nothing
	} else if ( ! SqlElement::isVisibleField($col) ) {
		// nothing 
	} else if ($planningType == 'portfolio' and !isset($desc[$col]['name'])) {
		// nothing 
	} else if ($planningType == 'planning' and !isset($desc[$col]['name'])) {
	  // nothing
	}else if ($planningType == 'portfolio' and isset($hiddenProjectField) and in_array(pq_strtolower(pq_substr($col, 0, 1)).pq_substr($col, 1), $hiddenProjectField)) {
		// nothing 
	} else if ($planningType == 'planning' and isset($hiddenActivityField) and in_array(pq_strtolower(pq_substr($col, 0, 1)).pq_substr($col, 1), $hiddenActivityField)) {
	  // nothing
	}else {
	  if (isNewGui()) {
	    if (! isset($desc[$col]['show'])) $desc[$col]['show']=0;
	    if ($col=='Name') {
  		  echo '<div style="position:relative;padding: 2px;width:100%;height:34px;cursor:default" id="columnSelector'.$col.'" >';		
  		  echo '<span style="display:inline-block;width:15px;float:left;"><img style="width:6px" src="css/images/iconNoDrag.gif" />&nbsp;&nbsp;</span>'; 
  		}elseif (!isset($contractGantt) and ($col=='ExterRes' or $col=='ObjectType')){
  		  echo '<div style="position:relative;padding: 2px;width:100%;height:34px;cursor:default;display:none;" class="dojoDndItem" id="columnSelector'.$col.'" dndType="planningColumn">';
  		  echo '<span style="float:left" class="dojoDndHandle handleCursor"><img style="width:10px;position:relative;top:8px;left:5px" src="css/images/iconDrag.gif" />&nbsp;&nbsp;</span>';
  		}else if (isset($contractGantt) && $col!='ExterRes' && $col!='ObjectType' && $col!='StartDate' && $col!='EndDate' && $col!='Resource' && $col!='IdStatus' &&  $col!='Duration'){
  		  echo '<div style="position:relative;padding: 2px;width:100%;height:34px;cursor:default;display:none;" class="dojoDndItem" id="columnSelector'.$col.'" dndType="planningColumn" >';
  		  echo '<span style="float:left" class="dojoDndHandle handleCursor"><img style="width:10px;position:relative;top:8px;left:5px" src="css/images/iconDrag.gif" />&nbsp;&nbsp;</span>';
  		}else if (!isset($portfolioPlanning) and ($col=='IdHealthStatus' or $col=='QualityLevel' or $col=='IdTrend' or $col=='IdOverallProgress')){
  		  echo '<div style="position:relative;padding: 2px;width:100%;height:34px;cursor:default;display:none;" class="dojoDndItem" id="columnSelector'.$col.'" dndType="planningColumn">';
  		  echo '<span style="float:left" class="dojoDndHandle handleCursor"><img style="width:10px;position:relative;top:8px;left:5px" src="css/images/iconDrag.gif" />&nbsp;&nbsp;</span>';
  		}else {
        echo '<div style="position:relative;padding: 2px;width:100%;height:34px;cursor:default" class="dojoDndItem" id="columnSelector'.$col.'" dndType="planningColumn">';
        echo '<span style="float:left;" class="dojoDndHandle handleCursor"><img style="width:10px;position:relative;top:8px;left:5px" src="css/images/iconDrag.gif" />&nbsp;&nbsp;</span>';
  		}
  		$disabledClass=($col=='Id' or $col=='Name' )?'mblSwitchDisabled':'';
  		echo '<div  id="checkColumnSelector'.$col.'Sw" class="colorSwitch '.$disabledClass.'" data-dojo-type="dojox/mobile/Switch" value="'.(($desc[$col]['show']==1)?'on':'off').'" leftLabel="" rightLabel="" ';
  		echo ' style="position:relative; float:left; left:5px;top:11px;z-index:99;" ';
  		echo '>';
  		echo '<script type="dojo/method" event="onStateChanged" >';
  		echo '  dijit.byId("checkColumnSelector'.$col.'").set("checked",(this.value=="on")?true:false);';
  		echo '</script>';
  		echo '</div>';
  	  echo '<span dojoType="dijit.form.CheckBox" type="checkbox" id="checkColumnSelector'.$col.'" style="display:none" ' 
  	    . (($desc[$col]['show']==1)?' checked="checked" ':'') 
  	    . (($col=='Name')?' readonly':'')
  	    . ' onChange="changePlanningColumn(\'' . $col . '\',this.checked,\'' . $order . '\',\'' . $planningType . '\');" '
  	    . '></span><label for="checkColumnSelector'.$col.'" class="checkLabel" style="position:relative;top:9px;float:none;left:15px;white-space:nowrap">';
  	  echo '&nbsp;';
  	  if($col=='ExterRes'){
  	    if(isset($objectClass) and $objectClass=='ClientContract'){
  	      echo i18n('colIdClient') . "</label>";
  	    }else if($objectClass=='SupplierContract'){
  	      echo i18n('colIdProvider') . "</label>";
  	    }
  	  }else if($col=='ValidatedStartDate'){
  	    echo i18n('colValidatedStart') . "</label>";
  	  }else if($col=='ValidatedEndDate'){
  	    echo i18n('colValidatedEnd') . "</label>";
  	  }else {
        $colName = pq_strtolower(pq_substr($col, 0, 1)).pq_substr($col, 1);
        if($planningType == 'portfolio' and property_exists('Project','_customFields') and in_array($colName, Project::$_customFields)){
          $project = new Project();
          $colName = $project->getColCaption($colName);
          echo $colName . "</label>";
        }else if($planningType == 'planning' and property_exists('Activity','_customFields') and in_array($colName, Activity::$_customFields)){
          $activity = new Activity();
          $colName = $activity->getColCaption($colName);
          echo $colName . "</label>";
        }else if($planningType == 'planning' and $col=='IdContact'){
          echo i18n('colRequestor') . "</label>";
        }else if($planningType == 'planning' and $col=='IdActivity'){
          echo i18n('colParentActivity') . "</label>";
        }else if ($planningType == 'portfolio' and $col=='IdContact'){
          echo i18n('colBillContact') . "</label>";
        }else if (($planningType == 'portfolio' or $planningType == 'planning') and $col=='IdUser'){
  	      echo i18n('colCreator') . "</label>";
        }else if (($planningType == 'portfolio' or $planningType == 'planning') and $col=='Responsible'){
  	      echo i18n('colManager') . "</label>";
  	    }else{
          echo i18n('col' . $col) . "</label>";
        }
  	  }
  	  echo '<div style="position:absolute; right:2px; top:0px;text-align:right">&nbsp;';
  	  echo '<div dojoType="dijit.form.NumberSpinner" id="planningColumnSelectorWidthId'.$order.'" ';
  	  echo ($desc[$col]['show']==0)?'disabled="disabled" ':'';
  	  echo ' onChange="changePlanningColumnWidth(\'' . $col . '\',this.value,\'' . $planningType . '\')"; ';
  	  echo ' constraints="{ min:'.($desc[$col]['minWidth']??50).', max:500, places:0 }"';
  	  echo ' style="width:50px; text-align: center;" value="'.htmlEncode($desc[$col]['width']).'" >';
  	  echo '</div>'; // NumberSpinner
  	  echo '&nbsp;</div>'; // style="float: right
  	  echo '</div>'; // id=columnSelector
	  } else {
	    //OLD GUI
  	  if ($col=='Name') {
  		  echo '<div style="padding: 2px;" id="columnSelector'.$col.'" >';		
  		  echo '<span style="display:inline-block;width:15px;"><img style="width:6px" src="css/images/iconNoDrag.gif" />&nbsp;&nbsp;</span>'; 
  		}elseif (!isset($contractGantt) and ($col=='ExterRes' or $col=='ObjectType')){
  		  echo '<div class="dojoDndItem" id="columnSelector'.$col.'" dndType="planningColumn" style="display:none;">';
  		  echo '<span class="dojoDndHandle handleCursor"><img style="width:6px" src="css/images/iconDrag.gif" />&nbsp;&nbsp;</span>';
  		}else if (isset($contractGantt) && $col!='ExterRes' && $col!='ObjectType' && $col!='StartDate' && $col!='EndDate' && $col!='Resource' && $col!='IdStatus' &&  $col!='Duration'){
  		  echo '<div class="dojoDndItem" id="columnSelector'.$col.'" dndType="planningColumn" style="display:none;">';
  		  echo '<span class="dojoDndHandle handleCursor"><img style="width:6px" src="css/images/iconDrag.gif" />&nbsp;&nbsp;</span>';
  		}else if (!isset($portfolioPlanning) and ($col=='IdHealthStatus' or $col=='QualityLevel' or $col=='IdTrend' or $col=='IdOverallProgress')){
  		  echo '<div class="dojoDndItem" id="columnSelector'.$col.'" dndType="planningColumn" style="display:none;">';
  		  echo '<span class="dojoDndHandle handleCursor"><img style="width:6px" src="css/images/iconDrag.gif" />&nbsp;&nbsp;</span>';
  		}else {
            echo '<div class="dojoDndItem" id="columnSelector'.$col.'" dndType="planningColumn">';
            echo '<span class="dojoDndHandle handleCursor"><img style="width:6px" src="css/images/iconDrag.gif" />&nbsp;&nbsp;</span>';
  		}
  	  echo '<span dojoType="dijit.form.CheckBox" type="checkbox" id="checkColumnSelector'.$col.'" ' 
  	    . (($desc[$col]['show']==1)?' checked="checked" ':'') 
  	    . (($col=='Name')?' readonly':'')
  	    . ' onChange="changePlanningColumn(\'' . $col . '\',this.checked,\'' . $order . '\',\'' . $planningType . '\');" '
  	    . '></span><label for="checkColumnSelector'.$col.'" class="checkLabel" style="white-space:nowrap">';
  	  echo '&nbsp;';
  	  if($col=='ExterRes'){
  	    if(isset($objectClass) and $objectClass=='ClientContract'){
  	      echo i18n('colIdClient') . "</label>";
  	    }else if($objectClass=='SupplierContract'){
  	      echo i18n('colIdProvider') . "</label>";
  	    }
  	  }else if ($planningType == 'planning' and $col=='IdContact'){
        echo i18n('colRequestor') . "</label>";
      }else if ($planningType == 'planning' and $col=='IdActivity'){
        echo i18n('colParentActivity') . "</label>";
  	  }else {
  	    echo i18n('col' . $col) . "</label>";
  	  }
  	  echo '<div style="float: right; text-align:right">&nbsp;';
  	  echo '<div dojoType="dijit.form.NumberSpinner" id="planningColumnSelectorWidthId'.$order.'" ';
  	  echo ($desc[$col]['show']==0)?'disabled="disabled" ':'';
  	  echo ' onChange="changePlanningColumnWidth(\'' . $col . '\',this.value,\'' . $planningType . '\')"; ';
  	  echo ' constraints="{ min:'.($desc[$col]['minWidth']??50).', max:500, places:0 }"';
  	  echo ' style="width:50px; text-align: center;" value="'.htmlEncode($desc[$col]['width']).'" >';
  	  echo '</div>'; // NumberSpinner
  	  echo '&nbsp;</div>'; // style="float: right
  	  echo '</div>'; // id=columnSelector
  	}
	}
}

?>
