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
 * Save a filter : call corresponding method in SqlElement Class
 * The new values are fetched in REQUEST
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/displayQuickFiletrList.php');
$referenceWidth = 45;
if(!isset($dontDisplay))$dontDisplay = false;
$globalQuickSearchRestrictProject='on';
if (sessionValueExists('globalQuickSearchRestrictProject') and getSessionValue('globalQuickSearchRestrictProject')==='off') {
  $globalQuickSearchRestrictProject='off';
}
$isPlanningQuickSearch=false;
$isPlanningScreen=(RequestHandler::isCodeSet('currentscreen') and RequestHandler::getValue('currentscreen')=='Planning');
  if(!isset($objectClass)){
    if($filterObjectClass)$objectClass=$filterObjectClass;
    if($objectClass){
//       $idClassType = "id". $objectClass. "Type";
      $idClassType = SqlElement::getTypeName($objectClass);
      $objectType = $idClassType;
    }
  }
  if ($isPlanningScreen and ($objectClass=='Activity' or $objectClass=='PlanningElement')) {
    $isPlanningQuickSearch=true;
    $dontDisplay=true;
  }
  if ($objectClass=='Planning' or $objectClass=='PlanningWorkPlan'){
    $isPlanningQuickSearch=($objectClass=='Planning');
    $objectClass='PlanningElement';
    $dontDisplay=true;
  } else if ($objectClass=='GlobalPlanning' or $objectClass=='VersionsPlanning' or $objectClass=='ResourcePlanning'){
    $isPlanningQuickSearch=($objectClass=='Planning');
    $objectClass='Activity';
    $dontDisplay=true;
  }
  else if ($objectClass=='ProjectDashboard'){
    $objectClass='Project';
    $dontDisplay=true;
  }
  if(!isset($obj)){
    if(isset($objectClass)){
      $obj=new $objectClass;
      $object = $obj;
    }
  }
  
  if(!isset($idClassType)){
    if(isset($objectClass)){
//       $idClassType = "id". $objectClass. "Type";
      $idClassType = SqlElement::getTypeName($objectClass);
      $objectType = $idClassType;
    }
  }
  
  if(!isset($objectClient)){
    $objectClient = '';
  }
  if(!isset($budgetParent)){
    $budgetParent = '';
  }
  $user=getSessionUser();
  $context="";
  $comboDetail=false;
  if (RequestHandler::isCodeSet('comboDetail')) {
    $comboDetail=true;
  }
$isGlobalQuickSearch=($objectClass=='GlobalView');
$quickSearchI18n=$isGlobalQuickSearch?'globalQuickSearch':'quickSearch';
$quickSearchHelp=$isGlobalQuickSearch
  ?i18n('helpGlobalQuickSearch')
  :i18n('helpQuickSearch', array(i18n('menu'.$objectClass)));
?>
<table style="width:100%;" id="quickFilterList">
     <?php if($isPlanningQuickSearch){ ?>
      <tr>
        <td>
          <table style="width:100%;margin:6px 0 10px 0;border-collapse:separate;border-spacing:0 6px;">
            <tr>
              <td></td>
              <td></td>
              <td></td>
              <td style="font-size:80%;font-style:italic;text-align:center;color:grey;line-height:12px;"><?php echo ucfirst(i18n("alwaysDisplay"));?></td>
            </tr>
            <tr>
              <td style="text-align:right;width:42px;padding-right:6px;vertical-align:middle;">
                <span style="text-transform:uppercase"><?php echo i18n("colId")?></span>
              </td>
              <td style="vertical-align:middle;width:150px;">
                <div title="<?php echo i18n('filterOnId')?>" style="width:150px" class="filterField rounded" dojoType="dijit.form.TextBox"
                  type="text" id="planningSearchIdQuick" name="planningSearchIdQuick">
                  <script type="dojo/method" event="onKeyUp" >
                    planningSearchInputKeyUp(event, 'id', 'quick');
                  </script>
                  <script type="dojo/method" event="onKeyDown" >
                    return planningSearchInputKeyDown(event, 'id', 'quick');
                  </script>
                </div>
              </td>
              <td style="vertical-align:middle;white-space:nowrap;padding-left:6px;">
                <span id="planningSearchIdCount" style="font-size:85%;display:inline-block;min-width:28px;">0/0</span>
                <span class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;display:inline-block;vertical-align:middle;transform: rotate(180deg);" title="<?php echo i18n('previous'); ?>" onclick="planningSearchMove('id', -1);"></span>
                <span class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;display:inline-block;vertical-align:middle;" title="<?php echo i18n('next'); ?>" onclick="planningSearchMove('id', 1);"></span>
              </td>
              <td style="vertical-align:middle;text-align:center;width:45px;">
                <div id="planningSearchIdQuickSw" name="planningSearchIdQuickSw" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if(sessionValueExists('planningSearchIdQuickSwPlanning')){ echo getSessionValue('planningSearchIdQuickSwPlanning'); }else{?>off<?php }?>" leftLabel="" rightLabel="">
                  <script type="dojo/method" event="onStateChanged" >
                    saveDataToSession('planningSearchIdQuickSwPlanning', this.value, true);
                    planningSearchToggleBar('id', this.value);
                  </script>
                </div>
              </td>
            </tr>
            <tr>
              <td style="text-align:right;width:42px;padding-right:6px;vertical-align:middle;">
                <span><?php echo ucfirst(i18n("colName"));?></span>
              </td>
              <td style="vertical-align:middle;width:150px;">
                <div title="<?php echo i18n('filterOnName')?>" style="width:150px" type="text" class="filterField rounded" dojoType="dijit.form.TextBox"
                    id="planningSearchNameQuick" name="planningSearchNameQuick">
                  <script type="dojo/method" event="onKeyUp" >
                    planningSearchInputKeyUp(event, 'name', 'quick');
                  </script>
                  <script type="dojo/method" event="onKeyDown" >
                    return planningSearchInputKeyDown(event, 'name', 'quick');
                  </script>
                </div>
              </td>
              <td style="vertical-align:middle;white-space:nowrap;padding-left:6px;">
                <span id="planningSearchNameCount" style="font-size:85%;display:inline-block;min-width:28px;">0/0</span>
                <span class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;display:inline-block;vertical-align:middle;transform: rotate(180deg);" title="<?php echo i18n('previous'); ?>" onclick="planningSearchMove('name', -1);"></span>
                <span class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;display:inline-block;vertical-align:middle;" title="<?php echo i18n('next'); ?>" onclick="planningSearchMove('name', 1);"></span>
              </td>
              <td style="vertical-align:middle;text-align:center;width:45px;">
                <div id="planningSearchNameQuickSw" name="planningSearchNameQuickSw" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if(sessionValueExists('planningSearchNameQuickSwPlanning')){ echo getSessionValue('planningSearchNameQuickSwPlanning'); }else{?>off<?php }?>" leftLabel="" rightLabel="">
                  <script type="dojo/method" event="onStateChanged" >
                    saveDataToSession('planningSearchNameQuickSwPlanning', this.value, true);
                    planningSearchToggleBar('name', this.value);
                  </script>
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
     <?php } ?>
     <?php if(!$dontDisplay){ ?> 
      <thead>
        <tr>
          <td class="titleQuickFilter" style="top: -10px;z-index: 9999999;border-radius:2px 2px 0 0;"><?php echo ucfirst(i18n("filters"));?>
            <span class="dijitDialogCloseIcon" onclick="dijit.byId('listFilterFilter').closeDropDown();" style="top:-3px; right:-2px;"></span>
          </td>
          <tr>
            <td style="height:10px;"></td>
          </tr>
          <td style="display:none;" >
            <button dojoType="dijit.form.Button" type="button" class="mediumTextButton">
              <?php echo i18n('buttonReset');?>
              <?php $listStatus = $object->getExistingStatus(); $lstStat=(count($listStatus));?>
              <?php $listTags = $object->getExistingTags(); $lstTags=(count($listTags));?>
              <script type="dojo/method" event="onClick">
                     var lstStat = <?php echo json_encode($lstStat); ?>;
                     var lstTag = <?php echo json_encode($lstTags); ?>;
                     resetFilterQuick(lstStat, lstTag);
                     resizeListDiv();
                     dijit.byId('listFilterFilter').closeDropDown();
             </script>
            </button>
          </td>
        </tr>
      </thead>
    

  <tr>
    <td>
      <table style="width:100%;">
        
        <!-- status and tags -->
        <?php if ((property_exists($obj, 'idStatus') and Parameter::getGlobalParameter('filterByStatus') == 'YES' and $objectClass!='GlobalView') or ( property_exists($obj, 'tags') and Parameter::getGlobalParameter('filterByTags') != 'NO' and $objectClass!='GlobalView')) {  ?>
        <tr>
          <td style="display:flex; justify-content:space-evenly; vertical-align:middle; font-size:100%; height:35px; width:100%; background-color:#f0f0f0; border-radius:10px;">         
          
          <?php if ( property_exists($obj, 'idStatus') and Parameter::getGlobalParameter('filterByStatus') == 'YES' and $objectClass!='GlobalView') {  ?> 
            <div style="display: flex; align-items: center;">
              <span><?php echo ucfirst(i18n("statusForFilter"));?>&nbsp;&nbsp;&nbsp;&nbsp;</span>
    	      <div style="position:relative;top:2px;">
          	    <?php  $paramDisplayByStatus = Parameter::getUserParameter('displayByStatusList_'.$objectClass);
          	    if($paramDisplayByStatus == 'block'){ $paramDisplayByStatus = 'on';}else{ $paramDisplayByStatus='off'; }?>
          		<div id="filterByStatusSwitch" name="filterByStatusSwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if(!$comboDetail and sessionValueExists('displayByStatusListSwitch'.$objectClass)){ echo getSessionValue('displayByStatusListSwitch'.$objectClass); }else{ echo $paramDisplayByStatus; }?>" leftLabel="" rightLabel="">
                  <script type="dojo/method" event="onStateChanged" >
                  var lstStat = <?php echo json_encode($lstStat); ?>;
                  saveDataToSession('displayByStatusListSwitch<?php echo $objectClass;?>',this.value);
                    if (dijit.byId('barFilterByStatus').domNode.style.display == 'none') {
				      dijit.byId('barFilterByStatus').domNode.style.display = 'block';
				    } else {
 				      dijit.byId('barFilterByStatus').domNode.style.display = 'none';
                      resetFilterQuick(lstStat);
				    }
				  dijit.byId('barFilterByStatus').getParent().resize();
                  saveDataToSession("displayByStatusList_<?php echo $objectClass;?>", dijit.byId('barFilterByStatus').domNode.style.display, true);
                  </script>
                </div>
      		  </div>
      		</div>
          <?php } ?>

          <?php if ( property_exists($obj, 'tags') and Parameter::getGlobalParameter('filterByTags') != 'NO' and $objectClass!='GlobalView') {  ?> 
            <div style="display: flex; align-items: center;">
              <span><?php echo ucfirst(i18n("colTags"));?>&nbsp;&nbsp;&nbsp;&nbsp;</span>
    		  <div>
    		    <?php  $paramDisplayByTags = Parameter::getUserParameter('displayByTagsList_'.$objectClass);
                if($paramDisplayByTags == 'block'){ $paramDisplayByTags = 'on';}else{ $paramDisplayByTags='off'; }?>
    			  <div style="position:relative;top:2px;" id="filterByTagsSwitch" name="filterByTagsSwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if(!$comboDetail and sessionValueExists('displayByTagsListSwitch'.$objectClass)){ echo getSessionValue('displayByTagsListSwitch'.$objectClass); }else{ echo $paramDisplayByTags; }?>" leftLabel="" rightLabel="">
                  <script type="dojo/method" event="onStateChanged" >
                    var lstTag = <?php echo json_encode($lstTags); ?>;
                    saveDataToSession('displayByTagsListSwitch<?php echo $objectClass;?>',this.value);
                    if (dijit.byId('barFilterByTags').domNode.style.display == 'none') {
				      dijit.byId('barFilterByTags').domNode.style.display = 'block';
				    } else {
				      dijit.byId('barFilterByTags').domNode.style.display = 'none';
                      resetFilterQuick(null, lstTag);
				    }
				    dijit.byId('barFilterByTags').getParent().resize();
                    saveDataToSession("displayByTagsList_<?php echo $objectClass;?>", dijit.byId('barFilterByTags').domNode.style.display, true);
                  </script>
                  </div>
    		    </div>
    		  </div>  
            <?php } ?>
          </td>
        </tr>
        <?php } ?>
        
        <tr style="width:100%;display:flex;margin:5px 0px;padding-bottom:5px;">
          <td style="width:30%"></td>
          <td style="width:60%"></td>
          <td style="width:10%; font-size:80%; font-style:italic; display:flex; justify-content:center; align-items:center; text-align:center; white-space:normal; color:grey; padding-right:5px;"><?php echo ucfirst(i18n("alwaysDisplay"));?></td>
        </tr>
        
        <!-- Id -->
        <?php if ($isPlanningQuickSearch) { ?>
        <tr style="width:100%;display:flex;gap:10px;">
          <td style="text-align:right;width:37%;min-width:120px;">
            <span class="" style="text-transform:uppercase"><?php echo i18n("colId")?><?php if (!isNewGui()) echo ':'?></span> 
          </td>
          <td style="width:53%; position:relative; top:-8px;">
            <table>
              <tr>
                <td>
                  <div title="<?php echo i18n('filterOnId')?>" style="width:<?php echo $referenceWidth*4;?>px" class="filterField rounded" dojoType="dijit.form.TextBox" 
                    type="text" id="planningSearchIdQuick" name="planningSearchIdQuick">
                    <script type="dojo/method" event="onKeyUp" >
                      planningSearchInputKeyUp(event, 'id');
                    </script>
                    <script type="dojo/method" event="onKeyDown" >
                      return planningSearchInputKeyDown(event, 'id');
                    </script>
                  </div>
                </td>
                <td style="padding-left:6px;white-space:nowrap;">
                  <span id="planningSearchIdCount" style="font-size:85%;">0/0</span>
                </td>
                <td style="padding-left:5px;">
                  <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;transform: rotate(180deg);" title="<?php echo i18n('previous'); ?>" onclick="planningSearchMove('id', -1);"></div>
                </td>
                <td>
                  <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;" title="<?php echo i18n('next'); ?>" onclick="planningSearchMove('id', 1);"></div>
                </td>
              </tr>
            </table>
          </td>
          <td style="width:10%;"></td>
        </tr>
        <?php } else { ?>
        <tr style="width:100%;display:flex;gap:10px;">
          <td style="text-align:right;width:37%;min-width:120px;">
            <span class="" style="text-transform:uppercase"><?php echo i18n("colId")?><?php if (!isNewGui()) echo ':'?></span> 
          </td>
          <td style="width:53%; position:relative; top:-8px;">
            <div title="<?php echo i18n('filterOnId')?>" style="width:<?php echo $referenceWidth*4;?>px" class="filterField rounded" dojoType="dijit.form.TextBox" 
                  type="text" id="listIdFilterQuick" name="listIdFilterQuick" value="<?php if(!$comboDetail and sessionValueExists('listIdFilter'.$objectClass)){ echo getSessionValue('listIdFilter'.$objectClass); }?>">
              <script type="dojo/method" event="onKeyUp" >
              if(dijit.byId('listIdFilterQuick').get('value') =='' && dijit.byId('listIdFilterQuickSw').get('value')=='off'){
                dojo.byId('filterDivsSpan').style.display="none";
                dijit.byId('listIdFilter').domNode.style.display = 'none';
              }else{
                if(dojo.byId('filterDivs').style.display=="none"){
                  dojo.byId('filterDivs').style.display="block";
                }
                dojo.byId('filterDivsSpan').style.display="block";
                dijit.byId('listIdFilter').domNode.style.display = 'block';
              }
              setTimeout("dijit.byId('listIdFilter').set('value',dijit.byId('listIdFilterQuick').get('value'))",10);
              setTimeout("filterJsonList('<?php echo $objectClass;?>');",10);
              resizeListDiv();
            </script>
            </div>
          </td>
          <td style="width:10%;text-align:center;">
            <div  style="position:relative;top:3px;" id="listIdFilterQuickSw" name="listIdFilterQuickSw" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if(sessionValueExists('listIdFilterQuickSw'.$objectClass)){ echo getSessionValue('listIdFilterQuickSw'.$objectClass); }else{?>off<?php }?>" leftLabel="" rightLabel="">
              <script type="dojo/method" event="onStateChanged" >
              saveDataToSession('listIdFilterQuickSw<?php echo $objectClass;?>',this.value,true);
              if(this.value=='on'){
                if(dojo.byId('filterDivs').style.display=="none"){
                  dojo.byId('filterDivs').style.display="block";
                }
                if(dojo.byId('filterDivsSpan').style.display=="none"){
                  dojo.byId('filterDivsSpan').style.display="block";
                  dijit.byId('listIdFilter').domNode.style.display = 'block';
                }
              }else{
                if(dojo.byId('filterDivsSpan').style.display=="block" && dijit.byId('listIdFilter').get('value')=='') {
                  dojo.byId('filterDivsSpan').style.display="none";
                  dijit.byId('listIdFilter').domNode.style.display = 'none';
                }
              }
              resizeListDiv();
            </script>
            </div>
          </td>
        </tr>
        <?php } ?>
        
      <!-- Name -->
      <?php if ( property_exists($obj,'name') or get_class($obj)=='Affectation') { ?>
      <?php if ($isPlanningQuickSearch) { ?>
      <tr style="width:100%;display:flex;gap:10px;"> 
        <td style="text-align:right;width:37%;min-width:120px;">
          <span class=""><?php echo ucfirst(i18n("colName"));?><?php if (!isNewGui()) echo ':';?></span> 
        </td>
        <td style="width:53%;position:relative; top:-8px;">
          <table>
            <tr>
              <td>
                <div title="<?php echo i18n('filterOnName')?>" style="width:<?php echo $referenceWidth*4;?>px" type="text" class="filterField rounded" dojoType="dijit.form.TextBox" 
                    id="planningSearchNameQuick" name="planningSearchNameQuick">
                  <script type="dojo/method" event="onKeyUp" >
                    planningSearchInputKeyUp(event, 'name');
                  </script>
                  <script type="dojo/method" event="onKeyDown" >
                    return planningSearchInputKeyDown(event, 'name');
                  </script>
                </div>
              </td>
              <td style="padding-left:6px;white-space:nowrap;">
                <span id="planningSearchNameCount" style="font-size:85%;">0/0</span>
              </td>
              <td style="padding-left:5px;">
                <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;transform: rotate(180deg);" title="<?php echo i18n('previous'); ?>" onclick="planningSearchMove('name', -1);"></div>
              </td>
              <td>
                <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;" title="<?php echo i18n('next'); ?>" onclick="planningSearchMove('name', 1);"></div>
              </td>
            </tr>
          </table>
        </td>
        <td style="width:10%;"></td>
      </tr>
      <?php } else { ?>
      <tr style="width:100%;display:flex;gap:10px;"> 
        <td style="text-align:right;width:37%;min-width:120px;">
          <span class=""><?php echo ucfirst(i18n("colName"));?><?php if (!isNewGui()) echo ':';?></span> 
        </td>
        <td style="width:53%;position:relative; top:-8px;">
          <div title="<?php echo i18n('filterOnName')?>" style="width:<?php echo $referenceWidth*4;?>px" type="text" class="filterField rounded" dojoType="dijit.form.TextBox" 
              id="listNameFilterQuick" name="listNameFilterQuick"  value="<?php if(!$comboDetail and sessionValueExists('listNameFilter'.$objectClass)){ echo getSessionValue('listNameFilter'.$objectClass); }?>">
            <script type="dojo/method" event="onKeyUp" >
             if(dijit.byId('listNameFilterQuick').get('value') =='' && dijit.byId('listNameFilterQuickSw').get('value')=='off'){
                dojo.byId('listNameFilterSpan').style.display="none";
                dijit.byId('listNameFilter').domNode.style.display = 'none';
              }else{
                if(dojo.byId('filterDivs').style.display=="none"){
                  dojo.byId('filterDivs').style.display="block";
                }
                dojo.byId('listNameFilterSpan').style.display="block";
                dijit.byId('listNameFilter').domNode.style.display = 'block';
              }
              dijit.byId('listNameFilter').set('value',dijit.byId('listNameFilterQuick').get('value'));
              setTimeout("filterJsonList('<?php echo $objectClass;?>');",10);
              resizeListDiv();
            </script>
          </div>
        </td>
        <td style="width:10%;text-align:center;position:relative;top:3px;">
          <div id="listNameFilterQuickSw" name="listNameFilterQuickSw" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if(sessionValueExists('listNameFilterQuickSw'.$objectClass)){ echo getSessionValue('listNameFilterQuickSw'.$objectClass); }else{?>off<?php }?>" leftLabel="" rightLabel="">
            <script type="dojo/method" event="onStateChanged" >
              saveDataToSession('listNameFilterQuickSw<?php echo $objectClass;?>',this.value,true);
              if(this.value=='on'){
                if(dojo.byId('filterDivs').style.display=="none"){
                  dojo.byId('filterDivs').style.display="block";
                }
                if(dojo.byId('listNameFilterSpan').style.display=="none"){
                    dojo.byId('listNameFilterSpan').style.display="block";
                    dijit.byId('listNameFilter').domNode.style.display = 'block';
                }
              }else{
                if(dojo.byId('listNameFilterSpan').style.display=="block" && dijit.byId('listNameFilter').get('value')=='') {
                  dojo.byId('listNameFilterSpan').style.display="none";
                  dijit.byId('listNameFilter').domNode.style.display = 'none';
                }
              }
              resizeListDiv();
            </script>
          </div>
        </td>
      </tr><?php }?>
      <?php }?>
      
      <!-- Type -->
      <?php if ( ( property_exists($obj,'id' . $objectClass . 'Type')) or ( $objectClass=='EmployeeLeaveEarned' and property_exists($obj,'idLeaveType')) ) { ?>
      <tr style="width:100%;display:flex;gap:10px;">
        <td style="text-align:right;width:37%;min-width:120px;"> <span class="nobr"><?php echo ucfirst(i18n("colType"));?><?php if (!isNewGui()) echo ':';?></span></td>
        <td style="width:53%;position:relative; top:-8px;">
         <select dojoType="dijit.form.FilteringSelect" class="input"  id="listTypeFilterQuick" name="listTypeFilterQuick"
          <?php echo autoOpenFilteringSelect();?>
            title="<?php echo i18n('helpLang');?>" style="width:<?php echo $referenceWidth*4;?>px" value="<?php if(!$comboDetail and sessionValueExists('listTypeFilter'.$objectClass)){ echo getSessionValue('listTypeFilter'.$objectClass); }?>">
            <script type="dojo/connect" event="onChange" >
              if( this.value ==' ' && dijit.byId('listTypeFilterQuickSw').get('value')=='off'){
                dojo.byId('listTypeFilterSpan').style.display="none";
                dijit.byId('listTypeFilter').domNode.style.display = 'none';
              }else{
                if(dojo.byId('filterDivs').style.display=="none"){
                  dojo.byId('filterDivs').style.display="block";
                }
                dojo.byId('listTypeFilterSpan').style.display="block";
                dijit.byId('listTypeFilter').domNode.style.display = 'block';
              }
              dijit.byId('listTypeFilter').set('value',this.value);
              refreshJsonList('<?php echo $objectClass;?>');
              resizeListDiv();
            </script>
            <?php  htmlDrawOptionForReference($idClassType, $objectType, $obj, false); ?>
          </select>
        </td>
        <td style="width:10%;text-align:center;position:relative;top:3px;">
          <div id="listTypeFilterQuickSw" name="listTypeFilterQuickSw" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if(sessionValueExists('listTypeFilterQuickSw'.$objectClass)){ echo getSessionValue('listTypeFilterQuickSw'.$objectClass); }else{?>off<?php }?>" leftLabel="" rightLabel="">
            <script type="dojo/method" event="onStateChanged" >
              saveDataToSession('listTypeFilterQuickSw<?php echo $objectClass;?>',this.value,true);
              if(this.value=='on'){
                if(dojo.byId('filterDivs').style.display=="none"){
                  dojo.byId('filterDivs').style.display="block";
                }
                if(dojo.byId('listTypeFilterSpan').style.display=="none"){
                    dojo.byId('listTypeFilterSpan').style.display="block";
                    dijit.byId('listTypeFilter').domNode.style.display = 'block';
                }
              }else{
                if(dojo.byId('listTypeFilterSpan').style.display=="block" && ( dijit.byId('listTypeFilter').get('value')=='' || dijit.byId('listTypeFilter').get('value')==' ' )) {
                  dojo.byId('listTypeFilterSpan').style.display="none";
                  dijit.byId('listTypeFilter').domNode.style.display = 'none';
                }
              }
              resizeListDiv();
            </script>
          </div>
         </td>
         </tr>
      <?php }?>
      
      <!-- client -->
      <?php if ( property_exists($obj,'idClient') ) { ?>
      <tr style="width:100%;display:flex;gap:10px;">
        <td style="text-align:right;width:37%;min-width:120px;"><span class="">&nbsp; <?php echo ucfirst(i18n("colClient"));?><?php if (!isNewGui()) echo ':';?></span></td>
        <td style="width:53%;position:relative; top:-8px;">
          <select title="<?php echo i18n('filterOnClient')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
            <?php echo autoOpenFilteringSelect();?> 
            data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
            id="listClientFilterQuick" name="listClientFilterQuick" style="width:<?php echo $referenceWidth*4;?>px" value="<?php if(!$comboDetail and sessionValueExists('listClientFilter'.$objectClass)){ echo getSessionValue('listClientFilter'.$objectClass); }?>" >
            <?php htmlDrawOptionForReference('idClient', $objectClient, $obj, false); ?>
            <script type="dojo/method" event="onChange" >
                    if(this.value ==' ' && dijit.byId('listClientFilterQuickSw').get('value')=='off'){
                      dojo.byId('listClientFilterSpan').style.display="none";
                      dijit.byId('listClientFilter').domNode.style.display = 'none';
                    }else{
                      if(dojo.byId('filterDivs').style.display=="none"){
                        dojo.byId('filterDivs').style.display="block";
                      }
                      dojo.byId('listClientFilterSpan').style.display="block";
                      dijit.byId('listClientFilter').domNode.style.display = 'block';
                    }
                    dijit.byId('listClientFilter').set('value',this.value);
                    refreshJsonList('<?php echo $objectClass;?>');
                    resizeListDiv();
                  </script>
          </select>
        </td>
        <td style="width:10%;text-align:center;position:relative;top:3px;">
          <div id="listClientFilterQuickSw" name="listClientFilterQuickSw" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if(!$comboDetail and sessionValueExists('listClientFilterQuickSw'.$objectClass)){ echo getSessionValue('listClientFilterQuickSw'.$objectClass); }else{?>off<?php }?>" leftLabel="" rightLabel="">
            <script type="dojo/method" event="onStateChanged" >
              saveDataToSession('listClientFilterQuickSw<?php echo $objectClass;?>',this.value,true);
              if(this.value=='on'){
                if(dojo.byId('filterDivs').style.display=="none"){
                  dojo.byId('filterDivs').style.display="block";
                }
                if(dojo.byId('listClientFilterSpan').style.display=="none"){
                    dojo.byId('listClientFilterSpan').style.display="block";
                    dijit.byId('listClientFilter').domNode.style.display = 'block';
                }
              }else{
                if(dojo.byId('listClientFilterSpan').style.display=="block" && ( dijit.byId('listTypeFilter').get('value')=='' || dijit.byId('listTypeFilter').get('value')==' ' )) {
                  dojo.byId('listClientFilterSpan').style.display="none";
                  dijit.byId('listClientFilter').domNode.style.display = 'none';
                }
              }
              resizeListDiv();
            </script>
          </div>
        </td>
      </tr>         
      <?php } ?>
      
      <!-- parent budget -->
      <?php if ( $objectClass == 'Budget' ) { ?>
        <tr style="width:100%;display:flex;gap:10px;">
          <td style="width:37%;text-align:right;min-width:120px;"><span class=""><?php echo ucfirst(i18n("colParentBudget"));?>&nbsp;<?php if (!isNewGui()) echo ':';?></span></td>
          <td style="width:53%;position:relative; top:-8px;">
            <select title="<?php echo i18n('filterOnBudgetParent')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                <?php echo autoOpenFilteringSelect();?> 
                data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                id="listBudgetParentFilterQuick" name="listBudgetParentFilterQuick" style="width:<?php echo $referenceWidth*4;?>px" value="<?php if(!$comboDetail and sessionValueExists('listBudgetParentFilter')){ echo getSessionValue('listBudgetParentFilter'); }?>" >
                  <?php 
                   htmlDrawOptionForReference('idBudgetItem',$budgetParent,$obj,false);?>
                  <script type="dojo/method" event="onChange" >
                    if(this.value ==' ' && dijit.byId('listBudgetParentFilterQuickSw').get('value')=='off'){
                      dojo.byId('listBudgetParentFilterSpan').style.display="none";
                      dijit.byId('listBudgetParentFilter').domNode.style.display = 'none';
                    }else{
                      if(dojo.byId('filterDivs').style.display=="none"){
                        dojo.byId('filterDivs').style.display="block";
                      }
                      dojo.byId('listBudgetParentFilterSpan').style.display="block";
                      dijit.byId('listBudgetParentFilter').domNode.style.display = 'block';
                    }
                    dijit.byId('listBudgetParentFilter').set('value',this.value);
                    refreshJsonList('<?php echo $objectClass;?>');
                    resizeListDiv();
                  </script>
          </select>
        </td>
        <td style="width:10%;text-align:center;position:relative;top:3px;">
          <div id="listBudgetParentFilterQuickSw" name="listBudgetParentFilterQuickSw" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if(!$comboDetail and sessionValueExists('listBudgetParentFilterQuickSw'.$objectClass)){ echo getSessionValue('listBudgetParentFilterQuickSw'.$objectClass); }else{?>off<?php }?>" leftLabel="" rightLabel="">
            <script type="dojo/method" event="onStateChanged" >
              saveDataToSession('listBudgetParentFilterQuickSw<?php echo $objectClass;?>',this.value,true);
              if(this.value=='on'){
                if(dojo.byId('filterDivs').style.display=="none"){
                  dojo.byId('filterDivs').style.display="block";
                }
                if(dojo.byId('listBudgetParentFilterSpan').style.display=="none"){
                    dojo.byId('listBudgetParentFilterSpan').style.display="block";
                    dijit.byId('listBudgetParentFilter').domNode.style.display = 'block';
                }
              }else{
                if(dojo.byId('listBudgetParentFilterSpan').style.display=="block" && (dijit.byId('listTypeFilter').get('value')=='' || dijit.byId('listTypeFilter').get('value')==' ' )){
                  dojo.byId('listBudgetParentFilterSpan').style.display="none";
                  dijit.byId('listBudgetParentFilter').domNode.style.display = 'none';
                }
              }
              resizeListDiv();
            </script>
          </div>
        </td>
      </tr>  
      <?php }?>        

      
      <!-- Quick search  -->
      <?php  if (! $comboDetail) {?>
       <tr style="width:100%;display:flex;gap:10px;">
         <td  style="width:37%;text-align:right;min-width:120px;"><span class=""><?php echo ucfirst(i18n($quickSearchI18n));?><?php if (!isNewGui()) echo ':';?></span></td>
         <td  style="width:53%;position:relative; top:-8px;max-width:195px;">
           <table>
            <tr>
              <td style="padding-right: 10px;">
                <input type="hidden" id="quickSearchValueQuickValue" name="quickSearchValueQuickValue" value="<?php if(sessionValueExists('listQuickSearchFilter'.$objectClass)){ echo getSessionValue('listQuickSearchFilter'.$objectClass); }?>" />
                <div title="<?php echo htmlEncode($quickSearchHelp,'quotes');?>" type="text" class="filterField rounded" dojoType="dijit.form.TextBox" 
                   id="quickSearchValueQuick" name="quickSearchValueQuick" style="width:150px;">
                  <script type="dojo/method" event="onKeyUp" >
                    var inputValue = dijit.byId('quickSearchValueQuick').get('value');
                    if(event.keyCode==13){
                      if(inputValue != ''){
                        quickSearchExecuteQuick('list');
                      }else{
                        quickSearchCloseQuick('list');
                      }
                    }
                    synchronizeQuickSearchQuickFilter(inputValue);
                  </script>
                  <script type="dojo/method" event="onBlur">
                    var inputValue = dijit.byId('listQuickSearchFilter').get('value');
                    if(inputValue == '') quickSearchCloseQuick('list');
                    else quickSearchExecuteQuick('list');
                  </script>
                </div>
              </td>
               <td>
                 <div class="roundedButtonSmall" style="width:22px;height:16px;border:0">
                   <div class="iconSize16 iconSearch iconSize16 generalColClass imageColorNewGui"
      	              title="<?php echo htmlEncode($quickSearchHelp,'quotes');?>" style="width:24px;height:24px;cursor:pointer;vertical-align:text-bottom;"
                      onclick="quickSearchExecuteQuick('quick');"
                    </div>
                 </div>
               </td>
               <td>
                <div class="roundedButtonSmall" style="position:relative; right:55px;width:16px;height:16px;border:0">
    	          <div class="iconSize16 iconCancel generalColClass imageColorNewGui"
    	           title="<?php echo i18n('comboCloseButton')?>"style="width:24px;height:24px;cursor:pointer;vertical-align:text-bottom;margin-right:5px;"
                  onclick="quickSearchCloseQuick('quick');"
                  </div>
                </div>
              </td>
            </tr>
          </table>
            </td>
            <td>
              <div style="width:10%;text-align:center;position:relative;top:3px;" id="quickSearchValueQuickSw" name="quickSearchValueQuickSw" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if(sessionValueExists('listQuickSearchFilterQuickSw'.$objectClass)){ echo getSessionValue('listQuickSearchFilterQuickSw'.$objectClass); }else{?>off<?php }?>" leftLabel="" rightLabel="">
                <script type="dojo/method" event="onStateChanged" >
                    saveDataToSession('listQuickSearchFilterQuickSw<?php echo $objectClass;?>',this.value,true);
                    if(this.value=='on'){
                      if(dojo.byId('filterDivs').style.display=="none"){
                        dojo.byId('filterDivs').style.display="block";
                      }
                      dojo.byId('listQuickSearchFilterSpan').style.display="block";
                      dijit.byId('listQuickSearchFilter').domNode.style.display = 'block';
                      dojo.byId('listQuickSearchFilterBtnSearch').style.display = 'block';
                      dojo.byId('listQuickSearchFilterBtnClose').style.display = 'block';
                    }else{
                      dojo.byId('listQuickSearchFilterSpan').style.display="none";
                      dijit.byId('listQuickSearchFilter').domNode.style.display = 'none';
                      dojo.byId('listQuickSearchFilterBtnSearch').style.display = 'none';
                      dojo.byId('listQuickSearchFilterBtnClose').style.display = 'none';
                    }
                    resizeListDiv();
                  </script>
              </div>
             </td> 
	    </tr>
	 <?php } ?>
     <?php if ($objectClass=='GlobalView') {?>
       <tr style="width:100%;display:flex;gap:10px;">
         <td style="width:10%;text-align:center;">
           <div id="globalQuickSearchRestrictProjectFilterSwitch"
             class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
             value="<?php echo $globalQuickSearchRestrictProject;?>"
             leftLabel="" rightLabel=""
             style="width:10px;position:relative;top:2px;z-index:99;">
             <script type="dojo/method" event="onStateChanged">
               setGlobalQuickSearchRestrictProject(this.value,'globalQuickSearchRestrictProjectFilterSwitch');
             </script>
           </div>
         </td>
         <td style="width:80%;text-align:left;min-width:250px;">
           <?php echo i18n('globalQuickSearchRestrictToSelectedProject');?>
         </td>
       </tr>
     <?php }?>
	 	   <tr>
	   <td style="text-align:right;padding:5px 5px 12px 0;" class="">
          <button dojoType="dijit.form.Button" type="button" class="mediumTextButton">
            <?php echo i18n('buttonReset');?>
            <?php $listStatus = $object->getExistingStatus(); $lstStat=(count($listStatus));?>
            <?php $listTags = $object->getExistingTags(); $lstTags=(count($listTags));?>
            <script type="dojo/method" event="onClick">
              var lstStat = <?php echo json_encode($lstStat); ?>;
              var lstTag = <?php echo json_encode($lstTags); ?>;
              resetFilterQuick(lstStat, lstTag);
              resizeListDiv();
              dijit.byId('listFilterFilter').closeDropDown();
            </script>
          </button>
        </td>
        </tr>
      
       <!-- sumOn -->
      <tr style="border-top:solid 1px;color:var(--color-medium);"><tr>
      <tr style="width:100%;display:flex;padding:18px 0 0 0;gap:10px;height:33px;">
        <td style="text-align:right;width:37%;min-width:120px;"> <span class=""><?php echo ucfirst(i18n("sumOnColumn"));?><?php if (!isNewGui()) echo ':';?></span></td>
        <td style="width:53%;position:relative; top:-8px;">
        <?php $curVal=Parameter::getUserParameter("listSumOnFilter$objectClass");?>
         <select type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect" id="listSumOnFilterQuick" name="listSumOnFilterQuick"
          <?php echo autoOpenFilteringSelect();?>
            title="<?php echo i18n('sumOnColumnHelp');?>" style="width:<?php echo $referenceWidth*4;?>px" value="<?php echo $curVal;?>">
            <option value=""></option>
            <?php 
            $objForList=new $objectClass();
            $fields=$objForList->listNumericFieldsForSum(false);
            asort($fields);
            foreach ($fields as $col=>$colName) {
              if((substr($col, -4) != 'Rate') and (substr($col, -3) != 'Pct') and ($col != 'priority') and ($col != 'minimumThreshold') and (substr($col, -5) != 'Value')  and ($col != 'nbVoted') and ($col != 'progress') and (substr($col, -8) != 'Progress') ) {
                echo "<option value='$col' ".(($col==$curVal)?"selected='selected'":"").">$colName</option>";
              }else{
                continue;
              }
            }
            ?>
            <script type="dojo/method" event="onChange" >
              saveDataToSession('listSumOnFilter<?php echo $objectClass;?>',this.value,true);
              refreshGrid(true);

              sumOnSw = dijit.byId('listSumOnFilterQuickSw').get("value");
              if((sumOnSw != "on") && (this.value != "")){
                 saveDataToSession('listSumOnFilterQuickSw<?php echo $objectClass;?>','on', true);
              }
              if(this.value == ""){
                 saveDataToSession('listSumOnFilterQuickSw<?php echo $objectClass;?>','off', true);
              }
              if(sumOnSw == 'on'){
                refreshGridSum();
                dojo.byId('filterDivs').style.display="block";
                dojo.byId('listSumOnFilterSpan').style.display="block";
                dojo.byId('listSumOnFilter').style.display = 'block';
              }else{
                dojo.byId('listSumOnFilterSpan').style.display="none";
                dojo.byId('listSumOnFilterSpan').innerHTML='';
                dojo.byId('listSumOnFilter').style.display = 'none';
                dojo.byId('listSumOnFilter').innerHTML='';
              }
              var idObj = document.querySelector('.dojoxGridRowSelected') ? parseInt(dojo.byId('objectId').value) : null;
              loadContent("objectMain.php?objectClass=" + '<?php echo $objectClass;?>',"centerDiv",null,false,false,idObj,false);
            </script>
          </select>
        </td>
        <td style="width:10%;text-align:center;position:relative;top:3px;">
        <?php $curValSw=Parameter::getUserParameter("listSumOnFilterQuickSw$objectClass");?>
          <div id="listSumOnFilterQuickSw" name="listSumOnFilterQuickSw" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if(sessionValueExists('listSumOnFilterQuickSw'.$objectClass)){ echo getSessionValue('listSumOnFilterQuickSw'.$objectClass); }else{?>off<?php }?>" leftLabel="" rightLabel="">
            <script type="dojo/method" event="onStateChanged" >
              saveDataToSession('listSumOnFilterQuickSw<?php echo $objectClass;?>',this.value, true);
              if(this.value=='on'){
                refreshGridSum();
                dojo.byId('filterDivs').style.display="block";
                dojo.byId('listSumOnFilterSpan').style.display="block";
                dojo.byId('listSumOnFilter').style.display = 'block';
              var idObj = document.querySelector('.dojoxGridRowSelected') ? parseInt(dojo.byId('objectId').value) : null;
              loadContent("objectMain.php?objectClass=" + '<?php echo $objectClass;?>',"centerDiv",null,false,false,idObj,false);
              }else{
                dojo.byId('listSumOnFilterSpan').style.display="none";
                dojo.byId('listSumOnFilterSpan').innerHTML='';
                dojo.byId('listSumOnFilter').style.display = 'none';
                dojo.byId('listSumOnFilter').innerHTML='';
              }
              resizeListDiv();
            </script>
          </div>
         </td>
        </tr>
        
     </table>
     <br>
     
     <?php } ?>
         
     <thead style="width: 100%;">
  <tr>
    <td class="titleQuickFilter"><?php echo i18n("advancedFilters");?></td>
  </tr>
  
</thead>
     
    
  </td></tr>
</table>
<br/> 
