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
scriptLog('   ->/view/objectList.php');

if (! isset($comboDetail)) {
  $comboDetail=false;
}
$objectClass=RequestHandler::getValue('objectClass',true);
Security::checkValidClass($objectClass);
$isGlobalQuickSearch=($objectClass=='GlobalView');
$quickSearchI18n=$isGlobalQuickSearch?'globalQuickSearch':'quickSearch';
$listQuickSearchI18n=$isGlobalQuickSearch?'listGlobalQuickSearch':'listQuickSearch';
$quickSearchHelp=$isGlobalQuickSearch
  ?i18n('helpGlobalQuickSearch')
  :i18n('helpQuickSearch', array(i18n('menu'.$objectClass)));
$objectType=RequestHandler::getValue('objectType',false,'');
$budgetParent=RequestHandler::getValue('budgetParent',false);
$objectClient=RequestHandler::getValue('objectClient',false,'');
$objectElementable=RequestHandler::getValue('objectElementable',false,'');
$idFavoriteProjectList = pq_trim(getSessionValue('idFavoriteProjectList'));
if(Parameter::getUserParameter('paramScreen_'.$objectClass)){
  $paramScreen=Parameter::getUserParameter('paramScreen_'.$objectClass);
}else{
  $paramScreen=Parameter::getUserParameter('paramScreen');
}

$obj=new $objectClass;

if (pq_array_key_exists('Directory', $_REQUEST)) {
  setSessionValue('Directory', $_REQUEST['Directory']);
} else {
  unsetSessionValue('Directory');
}
$multipleSelect=false;
if (pq_array_key_exists('multipleSelect', $_REQUEST)) {
  if ($_REQUEST['multipleSelect']) {
    $multipleSelect=true;
  }
}
$showIdle=(! $comboDetail and sessionValueExists('projectSelectorShowIdle') and getSessionValue('projectSelectorShowIdle')==1)?1:0;
$showIdlePossibleForProject=0;
//if ((Parameter::getUserParameter('showIdleDefault'))=='true') $showIdle=($showIdle==1)?0:1;
if (!$showIdle and $objectClass=='Project') {
  if (securityGetAccessRight('menuProject', 'read')=='ALL') { // If can see ALL projects, can show the "show idle" switch as visibility noe define from (possibly closed) allocation 
    $showIdlePossibleForProject=1;
  }
}
if ((Parameter::getUserParameter('showIdleDefault'))=='true') $showIdle=1;
if (! $comboDetail and is_array( getSessionUser()->_arrayFilters)) {
  if (pq_array_key_exists($objectClass, getSessionUser()->_arrayFilters)) {
    $arrayFilter=getSessionUser()->_arrayFilters[$objectClass];
    foreach ($arrayFilter as $filter) {
      if (isset($filter['sql']) and $filter['sql']['attribute']=='idle' and $filter['sql']['operator']=='>=' and $filter['sql']['value']=='0') {
        $showIdle=1;
      }
    }
  }
}
$displayWidth=RequestHandler::getNumeric('destinationWidth');
$displayWidthList="1980";
if (RequestHandler::isCodeSet('destinationWidth')) {
  //$displayWidthList=RequestHandler::getNumeric('destinationWidth');
}
$rightWidthVal=0;
if (isset($rightWidth)) {
  if (pq_substr($rightWidth,-1)=="%") {
    $rightWidthVal=(intval(pq_str_replace('%', '', $rightWidth))/100)*$displayWidthList;
  } else {
    $rightWidthVal=intval(pq_str_replace('px', '', $rightWidth));
  }
} else {
  $detailRightDivWidth=getContentPaneSize('contentPaneRightDetailDivWidth'.$objectClass);
  if (!$detailRightDivWidth) $detailRightDivWidth=0;
  if($detailRightDivWidth or $detailRightDivWidth==="0"){
    $rightWidthVal=$detailRightDivWidth;
  } else {
    $rightWidth=0;//15/100*$displayWidthList;
  }
}
$displayWidthList-=$rightWidthVal;

$hideTypeSearch=false;
$hideClientSearch=false;
$hideParentBudgetSearch=false;
$hideNameSearch=false;
$hideIdSearch=false;
$hideShowIdleSearch=false;
$hideEisSearch=false;
$hideQuickSearch=false;
$hideSumOnColumn=false;
$referenceWidth=50;
if ($comboDetail) {
  $screenWidth=getSessionValue('screenWidth',$displayWidthList);
  $displayWidthList=round($screenWidth*0.55,0)+150;
}
if(!isNewGui()){
if ($displayWidthList<1560 and $objectClass == 'Budget' ) {
  $hideClientSearch=true;
}
if ($displayWidthList<1400) {
  $referenceWidth=40;
  if ($displayWidthList<1250) {
    $hideParentBudgetSearch=true;
    $referenceWidth=30;
    if ($displayWidthList<1165) {
      $hideClientSearch=true;
      $hideEisSearch=true;
      $hideQuickSearch=true;
      if ($displayWidthList<1025) {
        $hideTypeSearch=true;
        if ($displayWidthList<700) {
          $hideIdSearch=true;
          $hideShowIdleSearch=true;
          if ($displayWidthList<650) {          
            $hideNameSearch=true;
            if ($displayWidthList<550) {
              $hideSumOnColumn=true;
            }
          }
        }
      }
    }
  }
}
}
$extrahiddenFields=$obj->getExtraHiddenFields('*','*');
if ($obj->isAttributeSetToField('idClient','hidden') or in_array('idClient',$extrahiddenFields)) $hideClientSearch=true;
if ($obj->isAttributeSetToField('idBudget','hidden') or in_array('idBudget',$extrahiddenFields)) $hideParentBudgetSearch=true;
if ($obj->isAttributeSetToField('id'.$objectClass.'Type','hidden') or in_array('id'.$objectClass.'Type',$extrahiddenFields)) $hideTypeSearch=true;

if ($comboDetail) $referenceWidth-=5;

$iconClassName=((SqlElement::is_subclass_of($objectClass, 'PlgCustomList'))?'ListOfValues':$objectClass);

$allProjectsChecked=false;
if (RequestHandler::getValue('objectClass')=='Project' and RequestHandler::getValue('mode')=='search') {
  $allProjectsChecked=true;
}

$arrayFilter=array('Id','Name','Type','Client','BudgetParent');
foreach ($arrayFilter as $filter) {
  $param='list'.$filter.'FilterQuickSw'.$objectClass;
  if (sessionValueExists($param)) {
    $userVal=Parameter::getUserParameter($param);
    if (pq_trim($userVal)) {
      setSessionValue($param, $userVal);
    }
  }
  
}
//session_write_close();
//Gautier saveParam
if(sessionValueExists('listTypeFilter'.$objectClass)){
  $listTypeFilter = getSessionValue('listTypeFilter'.$objectClass);
}else{
  $listTypeFilter = '';
}
if(sessionValueExists('listClientFilter'.$objectClass)){
  $listClientFilter = getSessionValue('listClientFilter'.$objectClass);
}else{
  $listClientFilter = '';
}
if(sessionValueExists('listElementableFilter'.$objectClass)){
  $listElementableFilter = getSessionValue('listElementableFilter'.$objectClass);
}else{
  $listElementableFilter = '';
}
if(sessionValueExists('listBudgetParentFilter') and $objectClass=='Budget'){
  $listBudgetParent = getSessionValue('listBudgetParentFilter');
}else{
  $listBudgetParent = '';
}
if(sessionValueExists('listShowIdle'.$objectClass)){
  $listShowIdle = getSessionValue('listShowIdle'.$objectClass);
  if($listShowIdle == "on"){
    $listShowIdle = true;
  }else{
    $listShowIdle = '';
  }
}else{
  $listShowIdle = '';
}

//objectStatus
$objectStatus = array();
$object = new $objectClass();
$cptStatus=0;
$filteringByStatus = false;
if (property_exists($objectClass,'idStatus')) {
  $listStatus = $object->getExistingStatus();
  foreach ($listStatus as $status) {
    $cptStatus += 1;
    if(sessionValueExists('showStatus'.$status->id.$objectClass)){
      if(getSessionValue('showStatus'.$status->id.$objectClass)=='true'){
        $filteringByStatus = true;
        $objectStatus[$cptStatus] = $status->id;
      }
    }
  }
}
$objectTags = array();
$cptTags=0;
$filteringByTags = false;
if (property_exists($objectClass,'tags')) {
  $listTags = $object->getExistingTags();
  foreach ($listTags as $tags) {
    $cptTags += 1;
    if(sessionValueExists('showTags'.$tags->id.$objectClass)){
      if(getSessionValue('showTags'.$tags->id.$objectClass)=='true'){
        $filteringByTags = true;
        $objectTags[$cptTags] = $tags->id;
      }
    }
  }
}
$extendedListZone=false;
$elementable=null;
if ( property_exists($obj,'idMailable') ) $elementable='idMailable';
else if (property_exists($obj,'idIndicatorable')) $elementable='idIndicatorable';
else if (property_exists($obj,'idTextable')) $elementable='idTextable';
else if ( property_exists($obj,'idChecklistable')) $elementable='idChecklistable';
else if ( property_exists($obj,'idSituationable')) $elementable='idSituationable';

//$soc = getSessionValue('listSumOnFilter'.$objectClass);
$soc=Parameter::getUserParameter('listSumOnFilter'.$objectClass);
$socSw=Parameter::getUserParameter('listSumOnFilterQuickSw'.$objectClass);
//$sumOnColum='';
//if($soc != ''){
//  if (property_exists($objectClass, $objectClass.'PlanningElement')) {
//    $pe = $objectClass."PlanningElement";
//    $objPE = new $pe();
//    if (property_exists($objPE, $soc)){
//      $sumOnColum =$objPE->sumSqlElementsFromCriteria($soc, null);
//    }
//  }else{
//    $sumOnColum = $obj->sumSqlElementsFromCriteria($soc, null);
//  }
//}
?>
<div dojoType="dojo.data.ItemFileReadStore" id="objectStore" jsId="objectStore" clearOnClose="true"
  url="../tool/jsonQuery.php?objectClass=<?php echo $objectClass;?>
&objectType=<?php echo $listTypeFilter; ?>
&objectClient=<?php echo $listClientFilter; ?>
&budgetParent=<?php echo $listBudgetParent; ?>
&objectElementable=<?php echo $listElementableFilter; ?>
<?php if($filteringByStatus){ foreach ($objectStatus as $id=>$statVal){ ?>
&objectStatus<?php echo $id;?>= <?php echo $statVal; } ?>
&countStatus=<?php echo $cptStatus; }?>
<?php if($filteringByTags){ foreach ($objectTags as $id=>$statVal){ ?>
&objectTags<?php echo $id;?>= <?php echo $statVal; } ?>
&countTags=<?php echo $cptTags; }?>
<?php if ($listShowIdle == true ) { ?> &idle=<?php echo $listShowIdle; }?>
<?php echo ($comboDetail)?'&comboDetail=true':'';?>
<?php echo ($showIdle)?'&idle=true':'';?>
<?php echo ($allProjectsChecked)?'&showAllProjects=on':'';?>
<?php echo Security::addTokenIndexToUrl();?>" >
</div>
<div dojoType="dijit.layout.BorderContainer" >
<div dojoType="dijit.layout.ContentPane" region="top" id="listHeaderDiv" style="width:50%;">
  <!-- QUICK SEARCH DIV --> 
  <form dojoType="dijit.form.Form" id="quickSearchListForm" action="" method="" >
    <script type="dojo/method" event="onSubmit" >
      quickSearchExecute();
      return false;        
    </script>
    <div class="listTitle" id="quickSearchDiv" 
       style="display:none; height:100%; width: 100%; position: absolute;z-index:9">
      <table >
        <tr height="100%" style="vertical-align: middle;">
          <td style="width:50px;min-width:50px" align="center">  
            <div style="position:absolute;left:0px;width:43px;top:0px;height:36px;" class="iconHighlight">&nbsp;</div>      
            <div style="z-index:9;position:absolute; top:0px;left:5px ;" class="icon<?php echo $iconClassName;?>32 icon<?php echo $iconClassName;?> iconSize32" /></div>    
          </td>
          <td><span class="title" id="classNameSpanQuickSearch"><?php echo i18n("menu" . $objectClass);?></span></td>
          <td style="text-align:right;" width="200px">
                  <span class="nobr">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                  <?php echo i18n($quickSearchI18n);?>
                  &nbsp;</span> 
          </td>
          <td style="vertical-align: middle;">
            <div title="<?php echo htmlEncode($quickSearchHelp,'quotes');?>" type="text" class="filterField rounded" dojoType="dijit.form.TextBox" 
               id="quickSearchValue" name="quickSearchValue"
               style="width:200px;">
            </div>
          </td>
  	      <td style="width:36px">            
  	        <button title="<?php echo htmlEncode($quickSearchHelp,'quotes');?>"  
  	          dojoType="dijit.form.Button" 
  	          id="listQuickSearchExecute" name="listQuickSearchExecute"
  	          iconClass="dijitButtonIcon dijitButtonIconSearch" class="detailButton" showLabel="false">
  	          <script type="dojo/connect" event="onClick" args="evt">
              //dijit.byId('quickSearchListForm').submit();
              quickSearchExecute();
            </script>
  	        </button>
  	      </td>      
          <td style="width:36px">
            <button title="<?php echo i18n('comboCloseButton')?>"  
              dojoType="dijit.form.Button" 
              id="listQuickSearchClose" name="listQuickSearchClose"
              iconClass="dijitButtonIcon dijitButtonIconUndo" class="detailButton" showLabel="false">
              <script type="dojo/connect" event="onClick" args="evt">
              quickSearchClose();
            </script>
            </button>
          </td>    
        </tr>
      </table>
    </div>
  </form>
  <!-- END QUICK SEARCH DIV --> 
  <table width="100%" class="listTitle" >
    <tr>
      <!-- ICON AND NAME -->
      <td style="width:50px;min-width:43px;" align="center">
         <div style="position:absolute;left:0px;width:43px;top:0px;height:36px;" class="iconHighlight">&nbsp;</div>
         <div style="position:absolute; top:3px;left:5px ;" class="icon<?php echo $iconClassName;?>32 icon<?php echo $iconClassName;?> iconSize32" /></div>
      </td>
      <td class="title" style="height:35px;width:30%;">    
        <div style="width:100%;height:100%;position:relative;">
          <div id="menuName" style="float:left;width:100%;position:absolute;top:8px;text-overflow:ellipsis;overflow:hidden;">
            <?php if (isNewGui()) {?>           
            <span id="gridRowCountShadow1" style="display:none;" class=""></span>
            <span id="gridRowCountShadow2" style="display:none;" class=""></span>
            <span id="gridRowCount" style="padding-left:5px" class=""></span>
            <?php }?> 
            <span id="classNameSpan" style="">
            <?php echo i18n("menu" . $objectClass);?>
            </span>
          </div>
        </div>
      </td>
      <!-- ALL OTHERS -->
      <td>   
        <form dojoType="dijit.form.Form" id="listForm" action="" method="" >
          <script type="dojo/method" event="onSubmit" >
            return false;        
          </script>  
          <input type="hidden" id="objectClass" name="objectClass" value="<?php echo $objectClass;?>" />  
          <input type="hidden" id="objectId" name="objectId" value="<?php if (isset($_REQUEST['objectId']))  { echo htmlEncode($_REQUEST['objectId']);}?>" />
          <input type="hidden" id="objectClassList" name="objectClassList" value="<?php echo $objectClass;?>" />          
          <table style="width: 100%; height: 39px;">
            <tr>
            <?php 
            if (isNewGui()) {
              $display = "none";
              if( (sessionValueExists('listIdFilter'.$objectClass) and getSessionValue('listIdFilter'.$objectClass)!='') or (sessionValueExists('listIdFilterQuickSw'.$objectClass) and getSessionValue('listIdFilterQuickSw'.$objectClass)=='on')
                  or (sessionValueExists('listNameFilter'.$objectClass) and getSessionValue('listNameFilter'.$objectClass)!='') or (sessionValueExists('listNameFilterQuickSw'.$objectClass) and getSessionValue('listNameFilterQuickSw'.$objectClass)=='on')
                  or (sessionValueExists('listTypeFilter'.$objectClass) and getSessionValue('listTypeFilter'.$objectClass)!='') or (sessionValueExists('listTypeFilterQuickSw'.$objectClass) and getSessionValue('listTypeFilterQuickSw'.$objectClass)=='on')
                  or (sessionValueExists('listQuickSearchFilter'.$objectClass) and getSessionValue('listQuickSearchFilter'.$objectClass)!='') or (sessionValueExists('listQuickSearchFilterQuickSw'.$objectClass) and getSessionValue('listQuickSearchFilterQuickSw'.$objectClass)=='on')
                  or (sessionValueExists('listClientFilter'.$objectClass) and getSessionValue('listClientFilter'.$objectClass)!='') or (sessionValueExists('listClientFilterQuickSw'.$objectClass) and getSessionValue('listClientFilterQuickSw'.$objectClass)=='on')
                  or $socSw=='on'
                  or (sessionValueExists('listBudgetParentFilter'.$objectClass) and getSessionValue('listBudgetParentFilter'.$objectClass)!='') or (sessionValueExists('listBudgetParentFilterQuickSw'.$objectClass) and getSessionValue('listBudgetParentFilterQuickSw'.$objectClass)=='on')
              ){
                $display = "block";
              }
              if ($elementable) $display = "block";
              ?>
              <td width="80%">&nbsp;</td>
              
               <!--  DIRECT FILTERS -->
               <td>
                 <div id="filterDivs" name="filterDivs" style="display:<?php echo $display;?>">
                   <table><tr>   
                   <?php  
                   if ( ! $hideIdSearch ) { ?>
                    <td style="text-align:right;" width="5px" class="allSearchTD idSearchTD allSearchFixLength">
                      <span id="filterDivsSpan" style="display:<?php echo sessionDisplayFilter('listIdFilter',$objectClass);?>" class="nobr">&nbsp;&nbsp;&nbsp;&nbsp;
                      <?php echo i18n("colId");?>
                      &nbsp;</span> 
                    </td>
                    <td width="5px" class="allSearchTD idSearchTD">
                      <div  style="display:<?php echo sessionDisplayFilter('listIdFilter',$objectClass); ?>" title="<?php echo i18n('filterOnId')?>" style="width:<?php echo $referenceWidth;?>px" class="filterField rounded" dojoType="dijit.form.TextBox" 
                       type="text" id="listIdFilter" name="listIdFilter" value="<?php if(!$comboDetail and sessionValueExists('listIdFilter'.$objectClass) ){ echo getSessionValue('listIdFilter'.$objectClass); }?>">
                        <script type="dojo/method" event="onKeyUp" >
                        setTimeout("filterJsonList('<?php echo $objectClass;?>');",10);
                        if(dijit.byId('listIdFilterQuick')){
                          if(dijit.byId('listIdFilterQuick').get('value') != dijit.byId('listIdFilter').get('value')){
                            dijit.byId('listIdFilterQuick').set('value',dijit.byId('listIdFilter').get('value'));
                          }
                        }
                      </script>
                      </div>
                  </td>
                  <?php }?>
              <?php if ( ! $hideNameSearch and (property_exists($obj,'name') or get_class($obj)=='Affectation')) { ?>
              <td style="text-align:right;" width="5px" class="allSearchTD nameSearchTD allSearchFixLength">
                <span id="listNameFilterSpan" style="display:<?php echo sessionDisplayFilter('listNameFilter',$objectClass); ?>" class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n("colName");?>
                &nbsp;</span> 
              </td>
              <td width="5px" class="allSearchTD nameSearchTD">
                <div title="<?php echo i18n('filterOnName')?>" type="text" class="filterField rounded" dojoType="dijit.form.TextBox" 
                id="listNameFilter" name="listNameFilter" style="display:<?php echo sessionDisplayFilter('listNameFilter',$objectClass); ?>; width:<?php echo $referenceWidth*2;?>px" value="<?php if(!$comboDetail and sessionValueExists('listNameFilter'.$objectClass)){ echo getSessionValue('listNameFilter'.$objectClass); }?>">
                  <script type="dojo/method" event="onKeyUp" >
                  	setTimeout("filterJsonList('<?php echo $objectClass;?>');",10);
                     if(dijit.byId('listNameFilterQuick')){
                          if(dijit.byId('listNameFilterQuick').get('value') != dijit.byId('listNameFilter').get('value')){
                            dijit.byId('listNameFilterQuick').set('value',dijit.byId('listNameFilter').get('value'));
                          }
                      }
                </script>
                </div>
              </td>
              <?php }?>              
              <?php 
// MTY - LEAVE SYSTEM        
              $idClassType = "id". $objectClass. "Type";
              if ( (!$hideTypeSearch and property_exists($obj,'id' . $objectClass . 'Type')) 
              or (!$hideTypeSearch and $objectClass=='EmployeeLeaveEarned' and property_exists($obj,'idLeaveType')) ) {
                if ($objectClass=="EmployeeLeaveEarned") {
                  $idClassType = "idLeaveType";
                } else {
                  $idClassType = "id". $objectClass. "Type";
                }
//              if ( !$hideTypeSearch and property_exists($obj,'id' . $objectClass . 'Type') ) { 
// MTY - LEAVE SYSTEM              
              ?>
              <td style="vertical-align: middle; text-align:right;" width="5px" class="allSearchTD typeSearchTD allSearchFixLength">
                 <span style="display:<?php echo sessionDisplayFilter('listTypeFilter',$objectClass); ?>" id="listTypeFilterSpan" class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n("colType");?>
                &nbsp;</span>
              </td>
              <td width="5px" class="allSearchTD typeSearchTD">
                <select title="<?php echo i18n('filterOnType')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                <?php echo autoOpenFilteringSelect();?> 
                id="listTypeFilter" name="listTypeFilter" style="display:<?php echo sessionDisplayFilter('listTypeFilter',$objectClass); ?>; width:<?php echo $referenceWidth*4;?>px" value="<?php if(!$comboDetail and sessionValueExists('listTypeFilter'.$objectClass)){ echo getSessionValue('listTypeFilter'.$objectClass); }?>">
                <?php 
// MTY - LEAVE SYSTEM              
                    htmlDrawOptionForReference($idClassType, $objectType, $obj, false); 
//                    htmlDrawOptionForReference('id' . $objectClass . 'Type', $objectType, $obj, false); 
// MTY - LEAVE SYSTEM              
                ?> <script type="dojo/method" event="onChange" >
                    refreshJsonList('<?php echo $objectClass;?>');
                     if(dijit.byId('listTypeFilterQuick')){
                          if(dijit.byId('listTypeFilterQuick').get('value') != dijit.byId('listTypeFilter').get('value')){
                            dijit.byId('listTypeFilterQuick').set('value',dijit.byId('listTypeFilter').get('value'));
                          }
                      }
                  </script>
                </select>
              </td>
              <?php }
              
              if ( !$hideQuickSearch){
              ?>
              <td style="vertical-align: middle; text-align:right;" width="5px" class="allSearchTD quickSearchSearchTD allSearchFixLength">
                 <span style="display:<?php echo sessionDisplayFilter('listQuickSearchFilter',$objectClass); ?>" id="listQuickSearchFilterSpan" class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n($listQuickSearchI18n);?>
                &nbsp;</span>
              </td>
              <td width="5px" class="allSearchTD quickSearchSearchTD">
                <table>
                <tr>
                  <td style="padding-right: 10px;">
                    <input type="hidden" id="listQuickSearchValueFilter" name="listQuickSearchValueFilter" value="" />
                    <div title="<?php echo htmlEncode($quickSearchHelp,'quotes');?>" type="text" class="filterField rounded" dojoType="dijit.form.TextBox" 
                       id="listQuickSearchFilter" name="listQuickSearchFilter" style="display:<?php echo sessionDisplayFilter('listQuickSearchFilter',$objectClass); ?>; width:<?php echo $referenceWidth*3;?>px">
                        <script type="dojo/method" event="onKeyUp" >
                        var inputValue = dijit.byId('listQuickSearchFilter').get('value');
                        saveDataToSession('listQuickSearchFilter<?php echo $objectClass;?>',inputValue,false);
                        if(event.keyCode==13){
                          if(inputValue != ''){
                            quickSearchExecuteQuick('list');
                          }else{
                            quickSearchCloseQuick('list');
                          }
                        }
                        if(dijit.byId('quickSearchValueQuick')){
                          if(dijit.byId('quickSearchValueQuick').get('value') != dijit.byId('listQuickSearchFilter').get('value')){
                            dijit.byId('quickSearchValueQuick').set('value',dijit.byId('listQuickSearchFilter').get('value'));
                          }
                        }
                        resizeListDiv();
                      </script>
                      <script type="dojo/method" event="onBlur">
                        var inputValue = dijit.byId('listQuickSearchFilter').get('value');
                        if(inputValue == '') quickSearchCloseQuick('list');
                        else quickSearchExecuteQuick('list');
                    </script>
                    </div>
                  </td>
                   <td>
                     <div id="listQuickSearchFilterBtnSearch" class="roundedButtonSmall" style="display:<?php echo sessionDisplayFilter('listQuickSearchFilter',$objectClass); ?>;width:22px;height:16px;border:0;">
                       <div class="iconSize16 iconSearch iconSize16 generalColClass imageColorNewGui"
          	              title="<?php echo htmlEncode($quickSearchHelp,'quotes');?>" style="width:24px;height:24px;cursor:pointer;vertical-align:text-bottom;margin-right:5px;"
                          onclick="quickSearchExecuteQuick('list');"
                        </div>
                     </div>
                   </td>
                   <td>
                    <div id="listQuickSearchFilterBtnClose" class="roundedButtonSmall" style="display:<?php echo sessionDisplayFilter('listQuickSearchFilter',$objectClass); ?>;width:16px;height:16px;border:0">
        	          <div class="iconSize16 iconCancel generalColClass imageColorNewGui"
        	           title="<?php echo i18n('comboCloseButton')?>"style="width:24px;height:24px;cursor:pointer;vertical-align:text-bottom;margin-right:5px;"
                      onclick="quickSearchCloseQuick('list');"
                    </div>
                    </div>
                    </td>
                    </tr>
                </table>
              </td>
              <?php }
              
              //--sumOn--
              if (!$hideSumOnColumn){
              ?>
              <td style="text-align:right;" width="5px" class="allSearchTD sumOnSearchTD allSearchFixLength">
                <input type='hidden' id='listSumOnFilterId' value='<?php echo $soc;?>' />
                <span id="listSumOnFilterSpan" style="display:<?php echo sessionDisplayFilter('listSumOnFilter',$objectClass); ?>" class="nobr"></span> 
              </td>
              <td width="5px" class="allSearchTD sumOnSearchTD allSearchFixLength" id="listSumOnFilterTd" style="">
                <div title="<?php echo i18n('sumOnColumnHelp')?>" class="display filterField rounded" readonly
                id="listSumOnFilter" name="listSumOnFilter" style="display:<?php echo sessionDisplayFilter('listSumOnFilter',$objectClass); ?>;">
                </div>
              </td>
              <?php }?>
              
              
              <!-- gautier #budgetParent  -->
              <?php if ( !$hideParentBudgetSearch and  $objectClass == 'Budget' ) { ?>
               <td style="vertical-align: middle; text-align:right;" width="5px" class="allSearchTD parentBudgetSearchTD allSearchFixLength">
                 <span id="listBudgetParentFilterSpan" style="display:<?php echo sessionDisplayFilter('listBudgetParentFilter',$objectClass);?>" class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n("colParentBudget");?>
                &nbsp;</span>
              </td>
              <td width="5px" class="allSearchTD parentBudgetSearchTD">
                <select title="<?php echo i18n('filterOnBudgetParent')?>" style="text-align:right;" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                <?php echo autoOpenFilteringSelect();?> 
                data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                id="listBudgetParentFilter" name="listBudgetParentFilter" style="display:<?php echo sessionDisplayFilter('listBudgetParentFilter',$objectClass);?>; width:<?php echo $referenceWidth*3;?>px" value="<?php if(!$comboDetail and sessionValueExists('listBudgetParentFilter')){ echo getSessionValue('listBudgetParentFilter'); }?>" >
                  <?php 
                   //gautier #indentBudget
                   htmlDrawOptionForReference('idBudgetItem',$budgetParent,$obj,false);?>
                  <script type="dojo/method" event="onChange" >
                    refreshJsonList('<?php echo $objectClass;?>');
                       if(dijit.byId('listBudgetParentFilterQuick')){
                          if(dijit.byId('listBudgetParentFilterQuick').get('value') != dijit.byId('listBudgetParentFilter').get('value')){
                            dijit.byId('listBudgetParentFilterQuick').set('value',dijit.byId('listBudgetParentFilter').get('value'));
                          }
                      }
                  </script>
                </select>
              </td>
              <!-- Ticket #3988	- Object list : boutton reset parameters  
                   florent
              -->
              <?php if ($hideClientSearch and $objectClass !='GlobalView') { ?>
              <td width="6px" class="allSearchTD resetSearchTD allSearchFixLength">
                <button dojoType="dijit.form.Button" type="button">
                    <?php echo i18n('buttonReset');?>
                    <?php $listStatus = $object->getExistingStatus(); $lstStat=(count($listStatus));?>
                    <?php $listTags = $object->getExistingTags(); $lstTags=(count($listTags));?>
                  <script type="dojo/method" event="onClick">
                     var lstStat = <?php echo json_encode($lstStat); ?>;
                     var lstTag = <?php echo json_encode($lstTags); ?>;
                     resetFilter(lstStat, lstTag);
                  </script>
                  
                </button>
              </td>      
              <?php }      
                      } 
                if ( !$hideClientSearch and property_exists($obj,'idClient') ) { ?>
              <td style="vertical-align: middle; text-align:right;" width="5px" class="allSearchTD clientSearchTD allSearchFixLength">
                 <span id="listClientFilterSpan" style="display:<?php echo sessionDisplayFilter('listClientFilter',$objectClass);?>" class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n("colClient");?>
                &nbsp;</span>
              </td>
              <td width="5px" class="allSearchTD clientSearchTD">
                <select title="<?php echo i18n('filterOnClient')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                <?php echo autoOpenFilteringSelect();?> 
                data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                id="listClientFilter" name="listClientFilter" style="display:<?php echo sessionDisplayFilter('listClientFilter',$objectClass);?>; width:<?php echo $referenceWidth*3;?>px" value="<?php if(!$comboDetail and sessionValueExists('listClientFilter'.$objectClass)){ echo getSessionValue('listClientFilter'.$objectClass); }?>" >
                  <?php htmlDrawOptionForReference('idClient', $objectClient, $obj, false); ?>
                  <script type="dojo/method" event="onChange" >
                    refreshJsonList('<?php echo $objectClass;?>');
                     if(dijit.byId('listClientFilterQuick')){
                          if(dijit.byId('listClientFilterQuick').get('value') != dijit.byId('listClientFilter').get('value')){
                            dijit.byId('listClientFilterQuick').set('value',dijit.byId('listClientFilter').get('value'));
                          }
                      }
                  </script>
                </select>
              </td>
        
              <?php } 
                 //$elementable=null;
                 if ($elementable) { ?>
              <td style="vertical-align: middle; text-align:right;" width="5px" class="allSearchTD elementSearchTD allSearchFixLength">
                 <span class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n("colElement");?>
                &nbsp;</span>
              </td>
              <td width="5px" class="allSearchTD elementSearchTD">
                <select title="<?php echo i18n('filterOnElement')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                <?php echo autoOpenFilteringSelect();?> 
                id="listElementableFilter" name="listElementableFilter" style="width:140px" value="<?php if(!$comboDetail and sessionValueExists('listElementableFilter'.$objectClass)){ echo getSessionValue('listElementableFilter'.$objectClass); }?>">
                  <?php htmlDrawOptionForReference($elementable, $objectElementable, $obj, false); ?>
                  <script type="dojo/method" event="onChange" >
                    refreshJsonList('<?php echo $objectClass;?>');
                  </script>
                </select>
              </td>
                
              
              <?php }                    
                  $activeFilter=false;
                 if (! $comboDetail and is_array(getSessionUser()->_arrayFilters)) {
                   if (pq_array_key_exists($objectClass, getSessionUser()->_arrayFilters)) {
                     if (count(getSessionUser()->_arrayFilters[$objectClass])>0) {
                     	//CHANGE qCazelles - Dynamic filter - Ticket #78
                     	//Old
                     	//$activeFilter=true;
                     	//New
                     	//A filter with isDynamic=1 is not active
                     	foreach (getSessionUser()->_arrayFilters[$objectClass] as $filter) {
                     		if (!isset($filter['isDynamic']) or $filter['isDynamic']=="0") {
                     			$activeFilter=true;
                     		}
                     	}
                     	//END CHANGE qCazelles - Dynamic filter - Ticket #78
                     }
                   }
                 } else if ($comboDetail and is_array(getSessionUser()->_arrayFiltersDetail)) {
                   if (pq_array_key_exists($objectClass, getSessionUser()->_arrayFiltersDetail)) {
                     if (count(getSessionUser()->_arrayFiltersDetail[$objectClass])>0) {
                     	//CHANGE qCazelles - Dynamic filter - Ticket #78
                     	//Old
                     	//$activeFilter=true;
                     	//New
                     	foreach (getSessionUser()->_arrayFiltersDetail[$objectClass] as $filter) {
                     	  //CHANGE qCazelles - Ticket 165
                     	  //Old
                     	  //if (!isset($filter['isDynamic']) or $filter['isDynamic']=="0") {
                     	  //New
                     		if ((!isset($filter['isDynamic']) or $filter['isDynamic']=="0") and (!isset($filter['hidden']) or $filter['hidden']=="0")) {
                     		//END CHANGE qCazelles - Ticket 165
                     			$activeFilter=true;
                     		}
                     	}
                     	//END CHANGE qCazelles - Dynamic filter - Ticket #78
                     }
                   }
                 } ?>
            <td >&nbsp;</td>
            <td width="5px"><span class="nobr">&nbsp;</span></td>
			      </tr></table></div><td>              
              
                          <?php if (! $comboDetail) {?> 
              <td width="36px" class="allSearchFixLength">
              <?php if ($objectClass=='GlobalView') {?>
                <div dojoType="dijit.form.DropDownButton"
                             class="comboButton"   
                             id="planningNewItem" jsId="planningNewItem" name="planningNewItem" 
                             showlabel="false" class="" iconClass="dijitButtonIcon dijitButtonIconNew"
                             title="<?php echo i18n('comboNewButton');?>">
                          <span>title</span>
                          <div dojoType="dijit.TooltipDialog" class="white" style="width:200px;">   
                            <div style="font-weight:bold; height:25px;text-align:center">
                            <?php echo i18n('comboNewButton');?>
                            </div>
                            <?php $arrayItems=GlobalView::getGlobalizables();
                            foreach($arrayItems as $item=>$itemName) {
                              $canCreate=securityGetAccessRightYesNo('menu' . $item,'create');
                              if ($canCreate=='YES') {
                                if (! securityCheckDisplayMenu(null,$item) ) {
                                  $canCreate='NO';
                                }
                              }
                              if ($canCreate=='YES') {?>
                              <div style="vertical-align:top;cursor:pointer;" class="dijitTreeRow"
                               onClick="addNewItem('<?php echo $item;?>');" >
                                <table width:"100%"><tr style="height:22px" >
                                <td style="vertical-align:top; width: 30px;padding-left:5px"><?php echo formatIcon($item, 22, null, false);;?></td>    
                                <td style="vertical-align:top;padding-top:2px"><?php echo i18n($item)?></td>
                                </tr></table>   
                              </div>
                              <div style="height:5px;"></div>
                              <?php } 
                              }?>
                          </div>
                        </div>
              <?php } else {?>
              <button id="newButtonList" dojoType="dijit.form.Button" showlabel="false"
                title="<?php echo i18n('buttonNew', array(i18n($_REQUEST['objectClass'])));?>"
                iconClass="dijitButtonIcon dijitButtonIconNew" class="detailButton">
                <script type="dojo/connect" event="onClick" args="evt">
                  hideExtraButtons('extraButtonsList');
		              dojo.byId("newButton").blur();
                  id=dojo.byId('objectId');
	                if (id) { 	
		                id.value="";
		                unselectAllRows("objectGrid");
                    if (switchedMode) {
                      setTimeout("hideList(null,true);", 1);
                    }
                    loadContent("objectDetail.php", "detailDiv", "listForm");
                    loadContentStream();
                  } else { 
                    showError(i18n("errorObjectId"));
	                }
                </script>
              </button>
              <?php }?>
            </td>
            <?php }?>

            <?php if (! $comboDetail) {
              $refreshAuto=(Parameter::getUserParameter('refreshAuto')!='')?Parameter::getUserParameter('refreshAuto'):0;?> 
              <td width="36px" class="allSearchFixLength">
                <button id="newButtonRefresh" dojoType="dijit.form.Button" showlabel="false"
                  title="<?php echo i18n('buttonRefreshList');?>"
                  iconClass="dijitButtonIcon <?php echo (!$refreshAuto)?'dijitButtonIconRefresh':'dijitButtonIconRefreshAuto';?>" class="detailButton">
                  <script type="dojo/connect" event="onClick" args="evt">
                    var idObj = document.querySelector('.dojoxGridRowSelected') ? parseInt(dojo.byId('objectId').value) : null;
                    hideExtraButtons('extraButtonsList');
	                 loadContent("objectMain.php?objectClass=" + '<?php echo $objectClass;?>',"centerDiv",null,false,false,idObj,false);
                  </script>
                </button>
              </td>    
			  <?php }?>
              
              
              
              <?php }?>
              
              
              
              
   
              <?php 
              //gautier #filterEnd
              if (!isNewGui()){ // ========================== NOT NEW GUI
                if ( ! $hideIdSearch ) { ?>
                  <td style="text-align:right;" width="5px" class="allSearchTD idSearchTD allSearchFixLength">
                    <span class="nobr">&nbsp;&nbsp;&nbsp;&nbsp;
                    <?php echo i18n("colId");?>
                    &nbsp;</span> 
                  </td>
                  <td width="5px" class="allSearchTD idSearchTD">
                    <div title="<?php echo i18n('filterOnId')?>" style="width:<?php echo $referenceWidth;?>px" class="filterField rounded" dojoType="dijit.form.TextBox" 
                     type="text" id="listIdFilter" name="listIdFilter" value="<?php if(!$comboDetail and sessionValueExists('listIdFilter'.$objectClass)){ echo getSessionValue('listIdFilter'.$objectClass); }?>">
                      <script type="dojo/method" event="onKeyUp" >
                    setTimeout("filterJsonList('<?php echo $objectClass;?>');",10);
                  </script>
                    </div>
                  </td>
                <?php 
                } // End if ( ! $hideIdSearch )?>
                <?php 
                if ( ! $hideNameSearch and (property_exists($obj,'name') or get_class($obj)=='Affectation')) { ?>
                  <td style="text-align:right;" width="5px" class="allSearchTD nameSearchTD allSearchFixLength">
                    <span class="nobr">&nbsp;&nbsp;&nbsp;
                      <?php echo i18n("colName");?>
                    &nbsp;</span> 
                  </td>
                  <td width="5px" class="allSearchTD nameSearchTD">
                    <div title="<?php echo i18n('filterOnName')?>" type="text" class="filterField rounded" dojoType="dijit.form.TextBox" 
                      id="listNameFilter" name="listNameFilter" style="width:<?php echo $referenceWidth*2;?>px" value="<?php if(!$comboDetail and sessionValueExists('listNameFilter'.$objectClass)){ echo getSessionValue('listNameFilter'.$objectClass); }?>">
                      <script type="dojo/method" event="onKeyUp" >
                  	setTimeout("filterJsonList('<?php echo $objectClass;?>');",10);
                  </script>
                    </div>
                  </td>
                <?php 
                } 
                // MTY - LEAVE SYSTEM        
                $idClassType = "id". $objectClass. "Type";
                if ( (!$hideTypeSearch and property_exists($obj,'id' . $objectClass . 'Type')) 
                or (!$hideTypeSearch and $objectClass=='EmployeeLeaveEarned' and property_exists($obj,'idLeaveType')) ) {
                  if ($objectClass=="EmployeeLeaveEarned") {
                    $idClassType = "idLeaveType";
                  } else {
                    $idClassType = "id". $objectClass. "Type";
                  }?>
                  <td style="vertical-align: middle; text-align:right;" width="5px" class="allSearchTD typeSearchTD allSearchFixLength">
                    <span class="nobr">&nbsp;&nbsp;&nbsp;<?php echo i18n("colType");?>&nbsp;</span>
                  </td>
                  <td width="5px" class="allSearchTD typeSearchTD">
                    <select title="<?php echo i18n('filterOnType')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                    <?php echo autoOpenFilteringSelect();?> 
                    id="listTypeFilter" name="listTypeFilter" style="width:<?php echo $referenceWidth*4;?>px" 
                    value="<?php if(!$comboDetail and sessionValueExists('listTypeFilter'.$objectClass)){ echo getSessionValue('listTypeFilter'.$objectClass); }?>">
                      <?php           
                        htmlDrawOptionForReference($idClassType, $objectType, $obj, false); 
                      ?>
                      <script type="dojo/method" event="onChange" >
                        refreshJsonList('<?php echo $objectClass;?>');
                      </script>
                    </select>
                  </td>
                <?php 
                } // End : if ( (!$hideTypeSearch?>
            <?php if ( $objectClass=='GlobalView') { ?>
              <td width="56px" class="allSearchTD resetSearchTD allSearchFixLength">
                <button dojoType="dijit.form.Button" type="button" >
                  <?php echo i18n('buttonReset');?>
                  <?php $listStatus = $object->getExistingStatus(); $lstStat=(count($listStatus));?>
                  <?php $listTags = $object->getExistingTags(); $lstTags=(count($listTags));?>
                  <script type="dojo/method" event="onClick">
                     var lstStat = <?php echo json_encode($lstStat); ?>;
                     var lstTag = <?php echo json_encode($lstTags); ?>;
                     resetFilter(lstStat, lstTag);
                  </script>
                </button>
              </td>
              <td style="vertical-align: middle; text-align:right;" width="5px">
                 <span class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n("listTodayItems");?>&nbsp;
              </td>
              
              <td width="5px">
                <div dojoType="dijit.form.DropDownButton"							    
  							  id="listItemsSelector" jsId="listItemsSelector" name="listItemsSelector" 
  							  showlabel="false" class="comboButton" iconClass="iconGlobalView iconSize22" 
  							  title="<?php echo i18n('itemSelector');?>">
                  <span>title</span>
  							  <div dojoType="dijit.TooltipDialog" class="white" id="listItemsSelectorDialog"
  							    style="position: absolute; top: 50px; right: 40%">   
                    <script type="dojo/connect" event="onShow" args="evt">
                      oldSelectedItems=dijit.byId('globalViewSelectItems').get('value');
                    </script>                 
                    <div style="text-align: center;position: relative;"> 
                      <button title="" dojoType="dijit.form.Button" 
                        class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonOK');?>
                        <script type="dojo/connect" event="onClick" args="evt">
                          dijit.byId('listItemsSelector').closeDropDown();
                        </script>
                      </button>
                      <div style="position: absolute;top: 34px; right:42px;"></div>
                    </div>   
                    <div style="height:5px;border-bottom:1px solid #AAAAAA"></div>    
  							    <div>                       
  							      <?php GlobalView::drawGlobalizableList();?>
  							    </div>
                    <div style="height:5px;border-top:1px solid #AAAAAA"></div>    
                    <div style="text-align: center;position: relative;">
                      <button title="" dojoType="dijit.form.Button" 
                         class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonOK');?>
                        <script type="dojo/connect" event="onClick" args="evt">
                          dijit.byId('listItemsSelector').closeDropDown();
                        </script>
                      </button>
                      <div style="position: absolute;bottom: 33px; right:42px;" ></div>
                    </div>   
  							  </div>
  							</div>                   
              </td>
              
            
            <?php }?>
            <?php  
            if (sessionValueExists('project')){
              $proj=getSessionValue('project');
              if(pq_strpos($proj, ",") != null){
              	$proj="+";
              }
            }else{
              $proj = '*';
            }
            if($comboDetail && property_exists($objectClass,'idProject') && $proj != '*'){
               ?> 
            <td style="width:200px;text-align: right; align: right;min-width:150px" >
                &nbsp;&nbsp;<?php echo i18n("showAllProjects");?>
            </td>
            <td style="width:10px;text-align: center; align: center;white-space:nowrap;">&nbsp;
              <div title="<?php echo i18n('showAllProjects')?>" dojoType="dijit.form.CheckBox" type="checkbox" class="whiteCheck"
                id="showAllProjects" name="showAllProjects" <?php if ($allProjectsChecked) echo "checked=ckecked"?>>
                <script type="dojo/method" event="onChange" >
                  refreshJsonList('<?php echo $objectClass;?>');
                </script>
              </div>&nbsp;
            </td>
            <?php }?>
              <!-- ADD qCazelles - Predefined Action -->
            <?php
				    if ($objectClass == 'Action' and Parameter::getGlobalParameter('enablePredefinedActions') == 'YES') { ?>
            <td style="vertical-align: middle; text-align:right;" width="5px">
               <span class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n("predefinedAction");?>
               &nbsp;</span>
            </td>
            <td width="5px">
              <select title="<?php echo i18n('predefinedAction')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
              <?php echo autoOpenFilteringSelect();?> 
              id="listPredefinedActions" name="listPredefinedActions" style="width:<?php echo $referenceWidth*4;?>px">                
                <?php htmlDrawOptionForReference('idPredefinedAction', null); ?>
                <script type="dojo/method" event="onChange" >
					        id=dojo.byId('objectId');
	        		    if (id) { 	
		    			      id.value="";
		     			      unselectAllRows("objectGrid");
					        }
					        loadContent("objectDetail.php", "detailDiv", 'listForm');
					        setTimeout(loadPredefinedAction, 100, "<?php echo getEditorType(); ?>");
                </script>
              </select>
            </td>
            <?php } ?>
              <!-- END ADD qCazelles -->
              
             <!-- Ticket #3988	- Object list : boutton reset parameters 
                   florent
              -->
             <?php 
             if (!$hideTypeSearch and $objectClass !='GlobalView') { ?>
               <?php 
               if ( $objectClass == 'Budget'  || property_exists($obj,'idClient') || property_exists($obj,'idMailable') || property_exists($obj,'idIndicatorable')|| property_exists($obj,'idTextable')|| property_exists($obj,'idChecklistable') || property_exists($obj,'idSituationable')) {
               }else {  
               ?>
             <td width="6px" class="allSearchTD resetSearchTD allSearchFixLength">
               <button dojoType="dijit.form.Button" type="button" >
                  <?php echo i18n('buttonReset');?>
                  <?php $listStatus = $object->getExistingStatus(); $lstStat=(count($listStatus));?>
                  <?php $listTags = $object->getExistingTags(); $lstTags=(count($listTags));?>
                  <script type="dojo/method" event="onClick">
                     var lstStat = <?php echo json_encode($lstStat); ?>;
                     var lstTag = <?php echo json_encode($lstTags); ?>;
                     resetFilter(lstStat, lstTag);
                  </script>
               </button>
             </td>
               <?php } ?>      
             <?php } ?> 
              
             <!-- gautier #budgetParent  -->
             <?php if ( !$hideParentBudgetSearch and  $objectClass == 'Budget' ) { ?>
             <td style="vertical-align: middle; text-align:right;" width="5px" class="allSearchTD parentBudgetSearchTD allSearchFixLength">
               <span class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n("colParentBudget");?>
                &nbsp;</span>
             </td>
             <td width="5px" class="allSearchTD parentBudgetSearchTD">
                <select title="<?php echo i18n('filterOnBudgetParent')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                <?php echo autoOpenFilteringSelect();?> 
                data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                id="listBudgetParentFilter" name="listBudgetParentFilter" style="width:<?php echo $referenceWidth*4;?>px" value="<?php if(!$comboDetail and sessionValueExists('listBudgetParentFilter')){ echo getSessionValue('listBudgetParentFilter'); }?>" >
                  <?php 
                   //gautier #indentBudget
                   htmlDrawOptionForReference('idBudgetItem',$budgetParent,$obj,false);?>
                  <script type="dojo/method" event="onChange" >
                    refreshJsonList('<?php echo $objectClass;?>');
                  </script>
                </select>
              </td>
              <!-- Ticket #3988	- Object list : boutton reset parameters  
                   florent
              -->
              <?php if ($hideClientSearch and $objectClass !='GlobalView') { ?>
              <td width="6px" class="allSearchTD resetSearchTD allSearchFixLength">
                <button dojoType="dijit.form.Button" type="button">
                    <?php echo i18n('buttonReset');?>
                    <?php $listStatus = $object->getExistingStatus(); $lstStat=(count($listStatus));?>
                    <?php $listTags = $object->getExistingTags(); $lstTags=(count($listTags));?>
                    <script type="dojo/method" event="onClick">
                      var lstStat = <?php echo json_encode($lstStat); ?>;
                      var lstTag = <?php echo json_encode($lstTags); ?>;
                      resetFilter(lstStat, lstTag);
                    </script>
                  
                </button>
              </td>      
              <?php } ?>     
              <?php } ?>
              <!-- end  -->
              
              <?php if ( !$hideClientSearch and property_exists($obj,'idClient') ) { ?>
              <td style="vertical-align: middle; text-align:right;" width="5px" class="allSearchTD clientSearchTD allSearchFixLength">
                 <span class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n("colClient");?>
                &nbsp;</span>
              </td>
              <td width="5px" class="allSearchTD clientSearchTD">
                <select title="<?php echo i18n('filterOnClient')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                <?php echo autoOpenFilteringSelect();?> 
                data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                id="listClientFilter" name="listClientFilter" style="width:<?php echo $referenceWidth*4;?>px" value="<?php if(!$comboDetail and sessionValueExists('listClientFilter'.$objectClass)){ echo getSessionValue('listClientFilter'.$objectClass); }?>" >
                  <?php htmlDrawOptionForReference('idClient', $objectClient, $obj, false); ?>
                  <script type="dojo/method" event="onChange" >
                    refreshJsonList('<?php echo $objectClass;?>');
                  </script>
                </select>
              </td>
              <!-- Ticket #3988	- Object list : boutton reset parameters  
                   florent
              -->
              <td width="6px" class="allSearchTD resetSearchTD allSearchFixLength">
                <button dojoType="dijit.form.Button" type="button" >
                    <?php echo i18n('buttonReset'); ?>
                    <?php $listStatus = $object->getExistingStatus(); $lstStat=(count($listStatus));?>
                    <?php $listTags = $object->getExistingTags(); $lstTags=(count($listTags));?>
                    <script type="dojo/method" event="onClick">
                      var lstStat = <?php echo json_encode($lstStat); ?>;
                      var lstTag = <?php echo json_encode($lstTags); ?>;
                      resetFilter(lstStat, lstTag);
                    </script>
                  
                </button>
              </td>           
              <?php } 
                 $elementable=null;
                 if ( property_exists($obj,'idMailable') ) $elementable='idMailable';
                 else if (property_exists($obj,'idIndicatorable')) $elementable='idIndicatorable';
                 else if (property_exists($obj,'idTextable')) $elementable='idTextable';
                 else if ( property_exists($obj,'idChecklistable')) $elementable='idChecklistable';
                 else if ( property_exists($obj,'idSituationable')) $elementable='idSituationable';
                 //$elementable=null;
                 if ($elementable) { ?>
              <td style="vertical-align: middle; text-align:right;" width="5px" class="allSearchTD elementSearchTD allSearchFixLength">
                 <span class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n("colElement");?>
                &nbsp;</span>
              </td>
              <td width="5px" class="allSearchTD elementSearchTD">
                <select title="<?php echo i18n('filterOnElement')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                <?php echo autoOpenFilteringSelect();?> 
                id="listElementableFilter" name="listElementableFilter" style="width:140px" value="<?php if(!$comboDetail and sessionValueExists('listElementableFilter'.$objectClass)){ echo getSessionValue('listElementableFilter'.$objectClass); }?>">
                  <?php htmlDrawOptionForReference($elementable, $objectElementable, $obj, false); ?>
                  <script type="dojo/method" event="onChange" >
                    refreshJsonList('<?php echo $objectClass;?>');
                  </script>
                </select>
              </td>
              <?php if($objectClass !='GlobalView'){?>
              <td width="6px " class="allSearchTD resetSearchTD allSearchFixLength">
                <button dojoType="dijit.form.Button" type="button" >
                    <?php echo i18n('buttonReset');?>
                    <?php $listStatus = $object->getExistingStatus(); $lstStat=(count($listStatus));?>
                    <?php $listTags = $object->getExistingTags(); $lstTags=(count($listTags));?>
                    <script type="dojo/method" event="onClick">
                      var lstStat = <?php echo json_encode($lstStat); ?>;
                      var lstTag = <?php echo json_encode($lstTags); ?>;
                      resetFilter(lstStat, lstTag);
                    </script>
                  
                </button>
              </td>      
              
              <?php }}?>                     
              <?php $activeFilter=false;
                 if (! $comboDetail and is_array(getSessionUser()->_arrayFilters)) {
                   if (pq_array_key_exists($objectClass, getSessionUser()->_arrayFilters)) {
                     if (count(getSessionUser()->_arrayFilters[$objectClass])>0) {
                     	//CHANGE qCazelles - Dynamic filter - Ticket #78
                     	//Old
                     	//$activeFilter=true;
                     	//New
                     	//A filter with isDynamic=1 is not active
                     	foreach (getSessionUser()->_arrayFilters[$objectClass] as $filter) {
                     		if (!isset($filter['isDynamic']) or $filter['isDynamic']=="0") {
                     			$activeFilter=true;
                     		}
                     	}
                     	//END CHANGE qCazelles - Dynamic filter - Ticket #78
                     }
                   }
                 } else if ($comboDetail and is_array(getSessionUser()->_arrayFiltersDetail)) {
                   if (pq_array_key_exists($objectClass, getSessionUser()->_arrayFiltersDetail)) {
                     if (count(getSessionUser()->_arrayFiltersDetail[$objectClass])>0) {
                     	//CHANGE qCazelles - Dynamic filter - Ticket #78
                     	//Old
                     	//$activeFilter=true;
                     	//New
                     	foreach (getSessionUser()->_arrayFiltersDetail[$objectClass] as $filter) {
                     	  //CHANGE qCazelles - Ticket 165
                     	  //Old
                     	  //if (!isset($filter['isDynamic']) or $filter['isDynamic']=="0") {
                     	  //New
                     		if ((!isset($filter['isDynamic']) or $filter['isDynamic']=="0") and (!isset($filter['hidden']) or $filter['hidden']=="0")) {
                     		//END CHANGE qCazelles - Ticket 165
                     			$activeFilter=true;
                     		}
                     	}
                     	//END CHANGE qCazelles - Dynamic filter - Ticket #78
                     }
                   }
                 }
                 ?>
            <td >&nbsp;</td>
            <td width="5px"><span class="nobr">&nbsp;</span></td>
            <!-- CHANGE qCazelles - Filter by status button is moved here -->
            <?php //Filter by status button is moved here
              if ( property_exists($obj, 'idStatus') and Parameter::getGlobalParameter('filterByStatus') == 'YES' and $objectClass!='GlobalView') {  ?>
            <td width="36px" class="listButtonClass">
            	<button title="<?php echo i18n('filterByStatus');?>"
			             dojoType="dijit.form.Button"
			             id="iconStatusButton" name="iconStatusButton"
			             iconClass="dijitButtonIcon dijitButtonIconStatusChange" class="detailButton" showLabel="false">
			             <script type="dojo/connect" event="onClick" args="evt">
                     protectDblClick(this);
						         if (dijit.byId('barFilterByStatus').domNode.style.display == 'none') {
							         dijit.byId('barFilterByStatus').domNode.style.display = 'block';
						         } else {
							         dijit.byId('barFilterByStatus').domNode.style.display = 'none';
						         }
						         dijit.byId('barFilterByStatus').getParent().resize();
                     saveDataToSession("displayByStatusList_<?php echo $objectClass;?>", dijit.byId('barFilterByStatus').domNode.style.display, true);
          				 </script>
			        </button>
			      </td>
			      
			     <?php  if (! $comboDetail or 1) {?>
			                </td>
			                      </td>
			                  <td width="36px" class="allSearchFixLength">
			                    <button title="<?php echo htmlEncode($quickSearchHelp,'quotes');?>"  
			                     dojoType="dijit.form.Button" 
			                     id="iconSearchOpenButton" name="iconSearchOpenButton"
			                     iconClass="dijitButtonIcon dijitButtonIconSearch" class="detailButton" showLabel="false">
			                      <script type="dojo/connect" event="onClick" args="evt">
			                        quickSearchOpen();
			                      </script>
			                    </button>
			                    <?php if (!isNewGui()) {?>
			                    <span id="gridRowCountShadow1" class="gridRowCountShadow1"></span>
			                    <span id="gridRowCountShadow2" class="gridRowCountShadow2"></span>              
			                    <span id="gridRowCount" class="gridRowCount"></span>         
			                    <?php }?>    
			                    <input type="hidden" id="listFilterClause" name="listFilterClause" value="" style="width: 50px;" />
			                  </td>
			      <?php }
			           } 
			            //gautier #filterEnd 
               }else{ //  ============================ NEW GUI

                   ?>
                   
                <?php if ( $objectClass=='GlobalView') { ?>

              <td width="5px">
                <div dojoType="dijit.form.DropDownButton"							    
  							  id="listItemsSelector" jsId="listItemsSelector" name="listItemsSelector" 
  							  showlabel="false" class="comboButton" iconClass="imageColorNewGui iconGlobalView iconSize22" 
  							  title="<?php echo i18n('itemSelector');?>">
                  <span>title</span>
  							  <div dojoType="dijit.TooltipDialog" class="white" id="listItemsSelectorDialog"
  							    style="position: absolute; top: 50px; right: 40%;">   
                    <script type="dojo/connect" event="onShow" args="evt">
                      oldSelectedItems=dijit.byId('globalViewSelectItems').get('value');
                    </script>                 
                    <div style="text-align: center;position: relative;"> 
                      <button title="" dojoType="dijit.form.Button" 
                        class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonOK');?>
                        <script type="dojo/connect" event="onClick" args="evt">
                          dijit.byId('listItemsSelector').closeDropDown();
                        </script>
                      </button>
                      <div style="position: absolute;top: 34px; right:42px;"></div>
                    </div>   
                    <div style="height:5px;border-bottom:1px solid #AAAAAA"></div>    
  							    <div>                       
  							      <?php GlobalView::drawGlobalizableList();?>
  							    </div>
                    <div style="height:5px;border-top:1px solid #AAAAAA"></div>    
                    <div style="text-align: center;position: relative;">
                      <button title="" dojoType="dijit.form.Button" 
                         class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonOK');?>
                        <script type="dojo/connect" event="onClick" args="evt">
                          dijit.byId('listItemsSelector').closeDropDown();
                        </script>
                      </button>
                      <div style="position: absolute;bottom: 33px; right:42px;" ></div>
                    </div>   
  							  </div>
  							</div>                   
              </td>
              <?php }?>
              
              <?php  if (sessionValueExists('project')){
                 $proj=getSessionValue('project');
                 if(pq_strpos($proj, ",") != null){
                 	$proj="+";
                 }
               }else{
                  $proj = '*';
               }
               if($comboDetail && property_exists($objectClass,'idProject') && ($proj != '*' || $idFavoriteProjectList)){
               ?> 
            <td style="width:200px;text-align: right; align: right;min-width:150px" >
                &nbsp;&nbsp;<?php echo i18n("showAllProjects");?>
              </td>
              <td style="width:10px;text-align: center; align: center;white-space:nowrap;">&nbsp;
                <div title="<?php echo i18n('showAllProjects')?>" dojoType="dijit.form.CheckBox" type="checkbox" class="whiteCheck"
                  id="showAllProjects" name="showAllProjects" <?php if ($allProjectsChecked) echo "checked=ckecked"?>>
                  <script type="dojo/method" event="onChange" >
                    refreshJsonList('<?php echo $objectClass;?>');
                  </script>
                </div>&nbsp;
              </td>
              <?php }?>  
                   
                   
               <!-- ADD qCazelles - Predefined Action -->
              <?php
				if ($objectClass == 'Action' and Parameter::getGlobalParameter('enablePredefinedActions') == 'YES') { ?>
              <td style="vertical-align: middle; text-align:right;" width="5px">
                 <span class="nobr">&nbsp;&nbsp;&nbsp;
                <?php echo i18n("predefinedAction");?>
                &nbsp;</span>
              </td>
              <td width="5px">
                <select title="<?php echo i18n('predefinedAction')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                <?php echo autoOpenFilteringSelect();?> 
                id="listPredefinedActions" name="listPredefinedActions" style="width:<?php echo $referenceWidth*4;?>px">                
                  <?php htmlDrawOptionForReference('idPredefinedAction', null); ?>
                  <script type="dojo/method" event="onChange" >
					         id=dojo.byId('objectId');
	        		     if (id) { 	
		    			     id.value="";
		     			     unselectAllRows("objectGrid");
					         }
					         loadContent("objectDetail.php", "detailDiv", 'listForm');
					         setTimeout(loadPredefinedAction, 100, "<?php echo getEditorType(); ?>");
                  </script>
                </select>
              </td>
              <?php } ?>
              <!-- END ADD qCazelles -->
                   

			      
			      <?php if (!isNewGui()) {?>
			      <span id="gridRowCountShadow1" class="gridRowCountShadow1"></span>
            <span id="gridRowCountShadow2" class="gridRowCountShadow2"></span>              
            <span id="gridRowCount" class="gridRowCount"></span>
            <?php }?>             
            <input type="hidden" id="listFilterClause" name="listFilterClause" value="" style="width: 50px;" />
<?php }
      if (! $comboDetail or 1) {?>            
            <td width="51px" class="allSearchFixLength">
              <button 
              title="<?php echo i18n('advancedFilter')?>"  
               class="comboButton"
               dojoType="dijit.form.DropDownButton" 
               id="listFilterFilter" name="listFilterFilter"
               iconClass="dijitButtonIcon icon<?php echo($activeFilter)?'Active':'';?>Filter" showLabel="false">
               <?php if (!isNewGui()){?>
                <script type="dojo/connect" event="onClick" args="evt">
                  showFilterDialog();
                </script>
                <script type="dojo/method" event="onMouseEnter" args="evt">
                  clearTimeout(closeFilterListTimeout);
                  clearTimeout(openFilterListTimeout);
                  openFilterListTimeout=setTimeout("dijit.byId('listFilterFilter').openDropDown();",popupOpenDelay);
                </script>
                <script type="dojo/method" event="onMouseLeave" args="evt">
                  clearTimeout(openFilterListTimeout);
                  closeFilterListTimeout=setTimeout("dijit.byId('listFilterFilter').closeDropDown();",2000);
                </script>
                <?php } ?>
                <div dojoType="dijit.TooltipDialog" id="directFilterList" style=" <?php if(isNewGui()){ ?> width:auto; max-width:400px;<?php }?> z-index: 999999;<!-- display:none; --> position: absolute;">
                  <?php 
                     if ($comboDetail) $_REQUEST['comboDetail']=true;
                     if(isNewGui())include "../tool/displayQuickFilterList.php";
                     include "../tool/displayFilterList.php";?>
                 <script type="dojo/method" event="onShow">
                    syncGlobalQuickSearchProjectSwitches();
                 </script>
                 <script type="dojo/method" event="onMouseEnter" args="evt">
                    clearTimeout(closeFilterListTimeout);
                    clearTimeout(openFilterListTimeout);
                </script>
                <script type="dojo/method" event="onFocus" args="evt">
                  if (dijit.byId('quickSearchValueQuick') && dijit.byId('listQuickSearchFilterValue')) dijit.byId('quickSearchValueQuick').set('value', dojo.byId('listQuickSearchFilterValue').value);
                </script>
                <?php if (!isNewGui()){ ?>
                <script type="dojo/method" event="onMouseLeave" args="evt">
                  dijit.byId('listFilterFilter').closeDropDown();
                </script>
                <?php }?>
                </div>
              </button>
            </td>
<?php }?>   
<?php if (! $comboDetail) {?>  
            <td width="51px" class="allSearchFixLength">           
							<div dojoType="dijit.form.DropDownButton"							    
							  id="listColumnSelector" jsId="listColumnSelector" name="listColumnSelector" 
							  showlabel="false" class="comboButton" iconClass="dijitButtonIcon dijitButtonIconColumn" 
							  title="<?php echo i18n('columnSelector');?>">
                <span>title</span>
							  <div dojoType="dijit.TooltipDialog" class="white" id="listColumnSelectorDialog"
							    style="position: absolute; top: 50px; right: 40%">   
                  <script type="dojo/connect" event="onHide" args="evt">
                    if (dndMoveInProgress) { this.show(); }
                  </script>
                  <script type="dojo/connect" event="onShow" args="evt">
                    sortListColumnSelector();
                    recalculateColumnSelectorName();
                  </script>                 
                  <div style="text-align: center;position: relative;"> 
                    <button dojoType="dijit.form.Button" title="<?php echo i18n('titleResetList');?>"
                      class="mediumTextButton" id="" name="" showLabel="true" ><?php echo i18n('buttonReset');?>
                      <script type="dojo/connect" event="onClick" args="evt">
                        resetListColumn();
                      </script>
                    </button>
                    <button title="" dojoType="dijit.form.Button" 
                      class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonManageLayout');?>
                      <script type="dojo/connect" event="onClick" args="evt">
                        showLayoutDialog('<?php echo $objectClass; ?>');
                      </script>
                    </button>
                    <button title="" dojoType="dijit.form.Button" 
                      class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonOK');?>
                      <script type="dojo/connect" event="onClick" args="evt">
                        validateListColumn();
                      </script>
                    </button>
                    <?php if (isNewGui()){?>
                    <div style="position: absolute;top: 6px; right:2px;" id="columnSelectorTotWidthTop"></div>
                    <?php } else {?>
                      <div style="position: absolute;top: 34px; right:42px;" id="columnSelectorTotWidthTop"></div>
                    <?php } ?>  
                  </div>  
                  <?php $screenHeight=getSessionValue('screenHeight','1080');
                    $columnSelectHeight=intval($screenHeight*0.6);?>
                  <div style="height:5px;border-bottom:1px solid #AAAAAA"></div>    
							    <div id="dndListColumnSelector" jsId="dndListColumnSelector" dojotype="dojo.dnd.Source"  
							      dndType="column" style="min-width:310px;overflow-y:auto; max-height:<?php echo $columnSelectHeight;?>px; position:relative"
							      withhandles="true" class="container">                       
							      <?php include('../tool/listColumnSelector.php')?>
							    </div>
                  <div style="height:5px;border-top:1px solid #AAAAAA"></div>    
                  <div style="text-align: center;position: relative;">
	                  <button dojoType="dijit.form.Button" title="<?php echo i18n('titleResetList');?>"
	                    class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonReset');?>
	                    <script type="dojo/connect" event="onClick" args="evt">
                        resetListColumn();
                      </script>
	                  </button>
	                  <button title="" dojoType="dijit.form.Button" 
                      class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonManageLayout');?>
                      <script type="dojo/connect" event="onClick" args="evt">
                        showLayoutDialog('<?php echo $objectClass; ?>');
                      </script>
                    </button>
                    <button title="" dojoType="dijit.form.Button" 
                       class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonOK');?>
                      <script type="dojo/connect" event="onClick" args="evt">
                        validateListColumn();
                      </script>
                    </button>
                    <?php if (isNewGui()){?>
                    <div style="position: absolute;bottom: 4px; right:2px;" id="columnSelectorTotWidthBottom"></div>
                    <?php } else {?>
                    <div style="position: absolute;bottom: 33px; right:42px;" id="columnSelectorTotWidthBottom"></div>
                    <?php } ?>  
                  </div>   
							  </div>
							</div>   
             </td>
<?php }?>                 
<?php if (! $comboDetail) {?>        
            <?php organizeListButtons();?>        
             <td width="36px" class="<?php if (! isNewGui()) echo 'allSearchFixLength';?>">
              <button title="<?php echo i18n('printList')?>"  
               dojoType="dijit.form.Button" 
               id="listPrint" name="listPrint"
               iconClass="dijitButtonIcon dijitButtonIconPrint" class="detailButton" showLabel="false">
                <script type="dojo/connect" event="onClick" args="evt">
                  showPrint('../tool/jsonQuery.php<?php echo Security::addTokenIndexToUrl('?')?>', 'list');
                </script>
              </button>
              </td>
<?php }?>            
<?php if (! $comboDetail) {?> 
<?php   $modePdf='Pdf';
        $modePdfChange='onlyPdf';
        if (SqlElement::class_exists('TemplateReport') and Plugin::isPluginEnabled('templateReport')) {
          $tmpMode=TemplateReport::getMode($objectClass,null,'list');
          if ($tmpMode=='multi') {$modePdf='download multi';}
          else if ($tmpMode=='download' or $tmpMode=='show') {$modePdf='download';}
          $modePdfChange=$modePdf;
        }
      ?> 
             <?php organizeListButtons();?>              
             <td width="36px" class="<?php if (! isNewGui()) echo 'allSearchFixLength';?>">
              <input type="hidden" style="width:32px" id="modePdfForPdfButton" value="<?php echo $modePdfChange;?>" />
              <button title="<?php echo ($modePdf=='pdf')?i18n('reportPrintPdf'):i18n('reportPrintTemplate');?>"
               dojoType="dijit.form.Button" 
               id="listPrintPdf" name="listPrintPdf"
               iconClass="dijitButtonIcon dijitButtonIcon<?php echo pq_ucfirst($modePdf);?>" class="detailButton" showLabel="false">
                <script type="dojo/connect" event="onClick" args="evt">
                 hideExtraButtons('extraButtonsList');
                 var modePdf=dojo.byId("modePdfForPdfButton").value;
                 if (<?php echo (SqlElement::class_exists('TemplateReport'))?'1':'0';?> && modePdf.substr(-5)=="multi") {
                  selectTemplateForReport('<?php echo $objectClass?>','list');
                 } else { 
                  showPrint("../tool/jsonQuery.php", 'list', null, 'pdf');
                 }
                </script>
              </button>              
            </td>
            <?php organizeListButtons();?>        
            <td width="36px" class="<?php if (! isNewGui()) echo 'allSearchFixLength';?>">
              <button title="<?php echo i18n('reportPrintCsv')?>"  
               dojoType="dijit.form.Button" 
               id="listPrintCsv" name="listPrintCsv"
               iconClass="dijitButtonIcon dijitButtonIconCsv" class="detailButton" showLabel="false">
                <script type="dojo/connect" event="onClick" args="evt">
                  hideExtraButtons('extraButtonsList');
                  openExportDialog('csv');
                  //showPrint("../tool/jsonQuery.php", 'list', null, 'csv');
                </script>
              </button>              
            </td>
            <?php if(Parameter::getGlobalParameter("ExportBillInFormatFacturX")=="YES" && $objectClass=="ProviderBill"){?>
            <?php organizeListButtons();?>        
            <td width="36px" class="<?php if (! isNewGui()) echo 'allSearchFixLength';?>">
              <button title="<?php echo i18n('importFacturX')?>"  
               dojoType="dijit.form.Button" 
               id="importFacturX" name="importFacturX"
               iconClass="iconSize22 iconButtonDownload" class="detailButton" showLabel="false">
                <script type="dojo/connect" event="onClick" args="evt">
                  hideExtraButtons('extraButtonsList');
                  var params="";
                  loadDialog('dialogImportFacturX', null, true, params);
                </script>
              </button>              
            </td>
            <?php }?>
<?php }?>

<?php if (! $comboDetail) {?>
            <?php organizeListButtons();?>        
             <td width="36px" class="<?php if (! isNewGui()) echo 'allSearchFixLength';?>">
              <button title="<?php echo i18n('saveAsReportList')?>"  
               dojoType="dijit.form.Button" 
               id="saveAsReportList" name="saveAsReportList"
               iconClass="iconReports22 iconReports iconSize22" class="detailButton" showLabel="false">
                <script type="dojo/connect" event="onClick" args="evt">
                  showReportLayoutDialog('<?php echo $objectClass; ?>');
                </script>
              </button>
              </td>
<?php }?>   

<?php if ( isNewGui()) {
    $objClassList = RequestHandler::getValue('objectClassList');
    $currentScreen=getSessionValue('currentScreen');
    if(Parameter::getUserParameter('paramRightDiv_'.$currentScreen)){
      $paramRightDiv=Parameter::getUserParameter('paramRightDiv_'.$currentScreen);
    }else{
      $paramRightDiv=Parameter::getUserParameter('paramRightDiv');
    }
    if($paramRightDiv=="bottom"){
      $activityStreamSize=getHeightLayoutActivityStream($currentScreen);
      $activityStreamDefaultSize=getDefaultLayoutSize('contentPaneRightDetailDivHeight');
    }else{
      $activityStreamSize=getWidthLayoutActivityStream($currentScreen);
      $activityStreamDefaultSize=getDefaultLayoutSize('contentPaneRightDetailDivWidth');
    }
    $user=getSessionUser();
    $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->getProfile($obj),'scope'=>'multipleUpdate'));
    $list=new ListYesNo($habil->rightAccess);
    $buttonMultiple=($list->code=='NO')?false:true;
    if ($buttonMultiple and !$comboDetail and ! pq_array_key_exists('planning',$_REQUEST) and $objectClass != 'GlobalView') {?>
    <?php organizeListButtons();?>
    <td width="36px" class="<?php if (! isNewGui()) echo 'allSearchFixLength';?>">
    <span id="multiUpdateButtonDiv" >
    <button id="multiUpdateButton" dojoType="dijit.form.Button" showlabel="false"
       title="<?php echo i18n('buttonMultiUpdate');?>"
       iconClass="dijitButtonIcon dijitButtonIconMultipleUpdate" class="detailButton">
        <script type="dojo/connect" event="onClick" args="evt">
          hideResultDivs();
          hideExtraButtons('extraButtonsList');
          var pos=<?php echo json_encode($paramRightDiv) ;?>;
          if (dijit.byId('detailRightDiv')) {
            if(pos=='bottom'){
              if(dijit.byId('detailRightDiv').h != 0){
                saveDataToSession('showActicityStream','show');
              }else{
                saveDataToSession('showActicityStream','hide');
              }
            }else{
              if(dijit.byId('detailRightDiv').w != 0){
                saveDataToSession('showActicityStream','show');
              }else{
                saveDataToSession('showActicityStream','hide');
              }
            }
          }
          hideStreamMode('false','<?php echo $paramRightDiv;?>','<?php echo $activityStreamDefaultSize;?>',false);
          startMultipleUpdateMode('<?php echo $objectClass;?>');  
          hideExtraButtons('extraButtonsDetail');
        </script>
    </button>
    </span>
    </td>
<?php }

    }
    if (! $comboDetail){
    organizeListButtons();
    switch ($paramScreen){
      case 'switch':
        $iconLayoutName="iconChangeLayout22 iconChangeLayout iconSize22";
        $buttonIconleft="horizontalLayoutClass";
        $buttonIconRight="verticalLayoutClass ";
        $buttonTitleLeft=i18n("showListTop");
        $buttonTitleRight=i18n("showListLeft");
        $parmLayoutLeft="top";
        $parmLayoutRight="left";
        break;
      case 'top':
        $iconLayoutName="horizontalLayoutClass";
        $buttonIconleft="iconChangeLayout22 iconChangeLayout iconSize22";
        $buttonIconRight="verticalLayoutClass ";
        $buttonTitleLeft=i18n("buttonSwitchedMode");
        $buttonTitleRight=i18n("showListLeft");
        $parmLayoutLeft="switch";
        $parmLayoutRight="left";
        break;
      default:
        $iconLayoutName="verticalLayoutClass ";
        $buttonIconleft="iconChangeLayout22 iconChangeLayout iconSize22";
        $buttonIconRight="horizontalLayoutClass";
        $buttonTitleLeft= i18n("buttonSwitchedMode");
        $buttonTitleRight=i18n("showListTop");
        $parmLayoutLeft="switch";
        $parmLayoutRight="top";
        break;
    }

    ?>
    <td width="36px" class="<?php if (! isNewGui()) echo 'allSearchFixLength';?>">
    <?php if(isNewGui()){?>
      <div dojoType="dijit.layout.ContentPane"  id="changeScreenLayout"  class="detailButton">
        <div  id="changeScreenLayoutAutherPos" style="display:none;background-color:var(--color-background);vertical-align:middle;<?php if( $parmLayoutLeft=='switch') echo 'width:86px;left:0px;';?>" >
          <table style="width: 100%;">
            <tr>
              <?php if($parmLayoutLeft!='switch'){ ?>
              
              <td style="width:33%;">
                <button id="changeScreenLayoutButton_<?php echo $parmLayoutLeft; ?>" dojoType="dijit.form.Button" showlabel="false" title="<?php echo $buttonTitleLeft;?>"
                  style="float:left;left: 6px;position: relative;"
                  iconClass="<?php echo $buttonIconleft;?>" class="detailButton">
                  <script type="dojo/connect" event="onClick" args="evt">
                    var pos=<?php echo json_encode($parmLayoutLeft) ;?>;
                    dojo.byId('changeScreenLayoutAutherPos').style.display="block";
                    hideResultDivs();
                    hideExtraButtons('extraButtonsList');
                    if(pos!="switch")switchModeLayout(pos,true);
                    else switchModeLayout(pos);
                    hideExtraButtons('extraButtonsDetail');
                  </script>
                </button>
              </td>
              <?php } ?>
              <td  style="width:34%;">
                <div id="changeScreenLayoutButtonCopy" class="pseudoButton selectedLayoutPos"  style="height:28px;position:relative;top:1px;left: 2px;" 
                onclick="dojo.byId('changeScreenLayoutAutherPos').style.display='none';dojo.byId('changeScreenLayoutButton').style.display='block';">
                     <div class="  <?php echo $iconLayoutName;?> imageColorNewGui" style="position:relative;left: 17%;top: 6%;" ></div>
                </div>
              </td>
              <td  style="width:33%;">
                <button id="changeScreenLayoutButton_<?php echo $parmLayoutRight; ?>" dojoType="dijit.form.Button" showlabel="false" title="<?php echo $buttonTitleRight;?>"
                  style="float:right;position:relative;right:3px;"
                 iconClass="<?php echo $buttonIconRight;?>" class="detailButton">
                  <script type="dojo/connect" event="onClick" args="evt">
                    var pos=<?php echo json_encode($parmLayoutRight) ;?>;
                    dojo.byId('changeScreenLayoutAutherPos').style.display="block";
                    hideResultDivs();
                    hideExtraButtons('extraButtonsList');
                    switchModeLayout(pos,true);
                    hideExtraButtons('extraButtonsDetail');
                  </script>
                </button>
              </td>
            </tr>
          </table>   
        </div>
        <button id="changeScreenLayoutButton" dojoType="dijit.form.Button" showlabel="false"
          title="<?php echo i18n('changeScreenLayout');?>"
           iconClass="<?php echo $iconLayoutName;?>" class="detailButton">
          <script type="dojo/connect" event="onClick" args="evt">
                dojo.byId('changeScreenLayoutAutherPos').style.display="block";
                dojo.byId('changeScreenLayoutButton').style.display="none";
          </script>
        </button>
      </div>
     <?php }else{?>
       <div dojoType="dijit.layout.ContentPane"  id="changeScreenLayout" class="pseudoButton" style="position:relative;overflow:hidden;width:50px;min-width:55px;">
        <div dojoType="dijit.form.DropDownButton"  title="<?php echo i18n("changeScreenLayout");?>" style="display: table-cell;background-color: #D3D3D3;vertical-align: middle;position:relative;min-width:50px;top:-3px" >
			    <table style="width:100%">
    			  <tr>
      				<td style="width:24px;margin-top:2px;">
      				  <div class="<?php if (!isNewGui()) echo 'iconChangeLayout22';?> iconChangeLayout iconSize22">&nbsp;</div> 
      				</td>
      			  <td style="vertical-align:middle;">&nbsp;</td>
    			  </tr>
			    </table>
  			    <div id="drawMenuLayoutScreen" dojoType="dijit.TooltipDialog"
               style="max-width:90px; overflow-x:hidden;width:90px; ">
               <?php include "menuLayoutScreen.php" ?>           
              </div> 
		</div>
      </div>
     <?php }?>
    </td>
 <?php }
  if (! $comboDetail) {            
    $extraPlgButtons=Plugin::getButtons('list', $objectClass);
    foreach ($extraPlgButtons as $bt) { ?>
    <?php organizeListButtons();?>
    <td width="36px" class="<?php if (! isNewGui()) echo 'allSearchFixLength';?>">
      <button id="pluginButtonList<?php echo $bt->id;?>" dojoType="dijit.form.Button" showlabel="false"
        title="<?php echo i18n($bt->buttonName);?>"
        iconClass="<?php echo $bt->iconClass;?>" class="detailButton">
        <script type="dojo/connect" event="onClick" args="evt">
          hideExtraButtons('extraButtonsList');
          <?php if ($bt->scriptJS) {?>
          <?php echo $bt->scriptJS;?>;
          <?php } else {?>
          loadContent("<?php echo $bt->scriptPHP;?>", "resultDivMain", "listForm", false);
          <?php }?>
        </script>
      </button>
    </td>
<?php }
     }?>             
          <?php organizeListButtonsEnd();?>      
     
     <?php if (! isNewGui()) {?>
                  <?php if (! $comboDetail) {?> 
              <td width="36px" class="allSearchFixLength">
                <!-- Global View : NEW ITEM DROPDOWN -->
                <?php if ($objectClass=='GlobalView') {?>
                <div dojoType="dijit.form.DropDownButton"
                 class="comboButton"   
                 id="planningNewItem" jsId="planningNewItem" name="planningNewItem" 
                 showlabel="false" class="" iconClass="dijitButtonIcon dijitButtonIconNew"
                 title="<?php echo i18n('comboNewButton');?>">
                  <span>title</span>
                  <div dojoType="dijit.TooltipDialog" class="white" style="width:200px;">   
                    <div style="font-weight:bold; height:25px;text-align:center">
                    <?php echo i18n('comboNewButton');?>
                    </div>
                    <?php $arrayItems=GlobalView::getGlobalizables();
                    foreach($arrayItems as $item=>$itemName) {
                      $canCreate=securityGetAccessRightYesNo('menu' . $item,'create');
                      if ($canCreate=='YES') {
                        if (! securityCheckDisplayMenu(null,$item) ) {
                          $canCreate='NO';
                        }
                      }
                      if ($canCreate=='YES') {?>
                      <div style="vertical-align:top;cursor:pointer;" class="dijitTreeRow"
                       onClick="addNewItem('<?php echo $item;?>');" >
                        <table width:"100%"><tr style="height:22px" >
                        <td style="vertical-align:top; width: 30px;padding-left:5px"><?php echo formatIcon($item, 22, null, false);;?></td>    
                        <td style="vertical-align:top;padding-top:2px"><?php echo i18n($item)?></td>
                        </tr></table>   
                      </div>
                      <div style="height:5px;"></div>
                      <?php 
                      } 
                    }?>
                  </div>
                </div>
                <?php } else {?>
                <!-- Not Global View : Single NEW BUTTON -->
                <button id="newButtonList" dojoType="dijit.form.Button" showlabel="false"
                  title="<?php echo i18n('buttonNew', array(i18n($_REQUEST['objectClass'])));?>"
                  iconClass="dijitButtonIcon dijitButtonIconNew" class="detailButton">
                  <script type="dojo/connect" event="onClick" args="evt">
                    hideExtraButtons('extraButtonsList');
		                dojo.byId("newButton").blur();
                    id=dojo.byId('objectId');
	                  if (id) { 	
		                  id.value="";
		                  unselectAllRows("objectGrid");
                      if (switchedMode) {
                        setTimeout("hideList(null,true);", 1);
                      }
                      loadContent("objectDetail.php", "detailDiv", "listForm");
                      loadContentStream();
                    } else { 
                      showError(i18n("errorObjectId"));
	                  }
                  </script>
                </button>
                <?php }?>
              </td>
              <?php } // End : if (!$comboDetail)?>             
              <!--  BUTTON REFRESH -->
              <?php $refreshAuto=(Parameter::getUserParameter('refreshAuto')!='')?Parameter::getUserParameter('refreshAuto'):0;?> 
              <td width="36px" class="allSearchFixLength">
                <button id="newButtonRefresh" dojoType="dijit.form.Button" showlabel="false"
                  title="<?php echo i18n('buttonRefreshList');?>"
                  iconClass="dijitButtonIcon <?php echo (!$refreshAuto)?'dijitButtonIconRefresh':'dijitButtonIconRefreshAuto';?>" class="detailButton">
                  <script type="dojo/connect" event="onClick" args="evt">
                     hideExtraButtons('extraButtonsList');
	                   refreshGrid(true);
                  </script>
                </button>
              </td>  
     
     <?php }?>     
          
<?php if ( property_exists($obj,'isEis') and !$hideEisSearch) { ?>
              <td style="vertical-align: middle; width:15%; min-width:<?php echo ($displayWidth>1200)?250:150;?>px; text-align:right;white-space:normal;" class="allSearchTD hideInServiceTD allSearchFixLength">
                <div style="max-height:32px;"> 
                <?php echo i18n("hideInService");?>
                </div>
              </td>
              <td style="width: 10px;text-align: center; align: center;white-space:nowrap;" class="allSearchTD hideInServiceTD allSearchFixLength">&nbsp;
                <?php $hideInService=Parameter::getUserParameter('hideInService');
                if (isNewGui()) htmlDrawSwitch('hideInService',($hideInService=='true')?1:0,true);?>
                <div title="<?php echo i18n('hideInService')?>" dojoType="dijit.form.CheckBox" 
                     class="whiteCheck" <?php if ($hideInService=='true') echo " checked ";?>
                     style="<?php if (isNewGui()) echo "display:none;";?>"
                     type="checkbox" id="hideInService" name="hideInService">
                 <script type="dojo/method" event="onChange" >
                  saveDataToSession('hideInService',((this.checked)?true:false),true);
                  setTimeout("refreshJsonList('<?php echo $objectClass;?>');",50);
                 </script>
                </div>&nbsp;
              </td>
              <?php }?> 
<?php if (! $hideShowIdleSearch and (! $comboDetail or $multipleSelect) ) {
            $visible=($objectClass=='Project' and !$showIdle and !$showIdlePossibleForProject)?false:true; ?>
            <td style="text-align: right; width:10%; min-width:50px;width:80px;white-space:normal;"  class="allSearchTD idleSearchTD allSearchFixLength">
              <span id="labelShowIdel" title="<?php echo i18n('showClosedProject')?>"  style="<?php echo (!$visible)?"display:none !important;":"";?>" ><?php echo i18n("labelShowIdleShort");?></span>
            </td>
            <td  title="<?php echo i18n('showClosedProject')?>" style="width: 10px;text-align: center; align: center;white-space:nowrap;" class="allSearchTD idleSearchTD allSearchFixLength">&nbsp;
              <?php if (isNewGui()) {?>
  		        <?php 
  		        if(!$comboDetail and sessionValueExists('listShowIdle'.$objectClass) and getSessionValue('listShowIdle'.$objectClass)== "on") $showIdle=1;
  		        if (isNewGui()) htmlDrawSwitch('listShowIdle',$showIdle,true,$visible);?>
  		        <?php }?>
              <div title="<?php echo i18n('labelShowIdle')?>" dojoType="dijit.form.CheckBox" style="<?php if (isNewGui() or (!isNewGui() and !$visible)) echo "display:none";?>"
                class="whiteCheck" <?php if ($showIdle) echo " checked ";?>
                type="checkbox" id="listShowIdle" name="listShowIdle"  value="<?php echo $showIdle; ?>">
                <script type="dojo/method" event="onChange" >
                  refreshJsonList('<?php echo $objectClass;?>');
                  <?php if($objectClass=='Budget'){?> refreshList('idBudgetParent','showIdle',dijit.byId('listShowIdle').get('value'),dijit.byId('listBudgetParentFilter').get('value'),'listBudgetParentFilter'); <?php } ?>
                </script>
              </div>
            </td>
<?php } ?>           
          </tr>
        </table>    
      </form>
    </td>
        
  </tr>
</table>
</div>

<?php if ( property_exists($obj, 'tags') and Parameter::getGlobalParameter('filterByTags') != 'NO') {
  $displayTags=Parameter::getUserParameter("displayByTagsList_$objectClass");
  if (!$displayTags) $displayTags='none';
?>

<?php 
  $object = new $objectClass();
  $listTags = $object->getExistingTags();
?>

<div class="listTitle" id="barFilterByTags" dojoType="dijit.layout.ContentPane" region="top" style="display: <?php echo $displayTags;?>;height:auto">
  <table style="display: block; width: 100%;padding-bottom:10px;">
    <tr style="width: 100%">
  	 <td style="font-weight:bold;padding-left:50px;vertical-align: top;padding-top: 5px;"><?php echo i18n("colTags");?>&nbsp;:&nbsp;</td>
  	 <td>
  	   <div style="width:100%;max-height:50px;">
  	     <table style="display: block; width: 100%">
          <tr style="width: 100%">
<?php
          $cptTags=0;
	      foreach ($listTags as $tags) {
		    $cptTags += 1;
		    $docLineclass = (sessionValueExists('showTags'.$tags->id.$objectClass) and getSessionValue('showTags'.$tags->id.$objectClass) == 'true')?'docLineTagNew':'docLineTag';
?>		
			<td style="float: left; height: 100%; white-space: nowrap" title="<?php echo i18n('selectTag', array($tags->name));?>">
			    <span class="<?php echo $docLineclass;?>" style="cursor:pointer;" onClick="updateShowTagState(this, <?php echo $cptTags; ?>);">
				  <div style="padding: 0px 5px 0px 5px;"><?php echo $tags->name; ?><div class="docLineTagPin"></div></div>
	            </span>
				<div style="position:relative;float:left;display:none;" id="showTags<?php echo $cptTags; ?>" 
				dojoType="dijit.form.CheckBox" type="checkbox" value="<?php echo $tags->id; ?>"
				<?php if(!$comboDetail and sessionValueExists('showTags'.$tags->id.$objectClass)){if(getSessionValue('showTags'.$tags->id.$objectClass)== 'true'){ ?> checked=" checked "<?php } }?> 
				onChange="refreshJsonList('<?php echo $objectClass; ?>');">
				</div>
			</td>
<?php
	      }
?>
          </tr>
         </table>
  	   </div>
  	 </td>
	 </tr>
	</table>
	<input type="hidden" id="countTags" value="<?php echo $cptTags; ?>" />
</div>
<?php 
} ?>

<!-- ADD by qCazelles - Filter by Status -->
<?php if ( property_exists($obj, 'idStatus') and Parameter::getGlobalParameter('filterByStatus') == 'YES') {
  $displayStatus=Parameter::getUserParameter("displayByStatusList_$objectClass");
  if (!$displayStatus) $displayStatus='none';
?>

<?php
$object = new $objectClass();
$listStatus = $object->getExistingStatus();
?>
  
<div class="listTitle" id="barFilterByStatus" dojoType="dijit.layout.ContentPane" region="top" style="display: <?php echo $displayStatus;?>;height:auto">
	<table style="display: block; width: 100%">
		<tr style="display: inlineblock; width: 100%">
			<td style="font-weight:bold;padding-left:50px;"><?php echo i18n("colIdStatus");?>&nbsp;:&nbsp;</td>
<?php
  $cptStatus=0;
	foreach ($listStatus as $status) {
		$cptStatus += 1;
		$docLineclass = 'docLineTag';
		$statusStyle = '';
		if(sessionValueExists('showStatus'.$status->id.$objectClass) and getSessionValue('showStatus'.$status->id.$objectClass) == 'true'){
    		$docLineclass = 'docLineTagNew';
    		$statusStyle = 'background-color:'.$status->color.';color:'.getForeColor($status->color).';';
		}
?>		
            <td style="float: left; height: 100%; white-space: nowrap" title="<?php echo i18n('selectStatus', array($status->name));?>">
			    <span class="<?php echo $docLineclass;?>" style="cursor:pointer;<?php echo $statusStyle;?>" onClick="updateShowStatusState(this, <?php echo $cptStatus; ?>, '<?php echo $status->color;?>');">
				  <div style="padding: 0px 5px 0px 5px;"><?php echo $status->name; ?><div class="docLineTagPin"></div></div>
	            </span>
				<div style="position:relative;float:left;display:none;" id="showStatus<?php echo $cptStatus; ?>"
				  dojoType="dijit.form.CheckBox" type="checkbox" value="<?php echo $status->id; ?>"
				  <?php if(!$comboDetail and sessionValueExists('showStatus'.$status->id.$objectClass)){if(getSessionValue('showStatus'.$status->id.$objectClass) == 'true'){ ?> checked=" checked "<?php } }?> 
				  onChange="refreshJsonList('<?php echo $objectClass; ?>');">
				</div>
			</td>
<?php
	 } ?>
		</tr>
	</table>
	<input type="hidden" id="countStatus" value="<?php echo $cptStatus; ?>" />
</div>
<?php 
} ?>
<!-- END ADD qCazelles -->
<div dojoType="dijit.layout.ContentPane" region="center" id="gridContainerDiv">
<div class="contextMenuClass comboButtonInvisible" dojoType="dijit.form.DropDownButton" id="objectContextMenu" name="objectContextMenu" style="position:absolute;top:0px;left:0px;width:0px;height:0px;overflow:hidden;">
      <div dojoType="dijit.TooltipDialog" id="dialogObjectContextMenu" tabindex="0"" onMouseEnter="clearTimeout(hideObjectContextMenu);" onMouseLeave="hideObject(200)" onfocusout="hideElementOnFocusOut(null, hideObject(200))">
        <input type="hidden" id="contextMenuRefId" name="contextMenuRefId" value="" />
        <input type="hidden" id="contextMenuRefType" name="contextMenuRefType" value="" />
        <input type="hidden" id="objectClassRow" name="objectClassRow" value="" />
        <input type="hidden" id="objectIdRow" name="objectIdRow" value="" />
        <table style="width:100%;height:100%">
          <tr id='addFromObject' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Add', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='addFromObject_label'><?php echo i18n('contextMenuButtonNew');?></td>
          </tr>
          <tr id='copyFromObject' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Copy', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='copyFromObject_label'><?php echo i18n('contextMenuButtonCopy');?></td>
          </tr>
          <tr id='removeFromObject' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Remove', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='removeFromObject_label'><?php echo i18n('contextMenuButtonDelete');?></td>
          </tr>
          <tr id='printFromObject' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Print', true , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='printFromObject_label'><?php echo i18n('contextMenuButtonPrint');?></td>
          </tr>
          <tr id='printPdfFromObject' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Pdf', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='printPdfFromObject_label'><?php echo i18n('reportPrintPdf');?></td>
          </tr>
          <tr id='mailFromObject' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Email', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='mailFromObject_label'><?php echo i18n('contextMenuButtonMail');?></td>
          </tr>
          <tr id='searchFromObject' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('SearchPlanning', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='searchFromObject_label'><?php echo i18n('buttonSearch');?></td>
          </tr>
          <tr id='selectFromObject' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('SelectObject', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='selectFromObject_label'><?php echo i18n('SelectProject');?></td>
          </tr>
        </table>
      </div>
    </div>
    
<?php
$savedSort = null;
$sessionId = 'listSort_' . $objectClass;
if (sessionValueExists($sessionId)) {
  $sortData = getSessionValue($sessionId);
  if ($sortData && strpos($sortData, '|') !== false) {
    list($field, $order) = explode('|', $sortData);
    $savedSort = array(
      'field' => $field,
      'order' => $order
    );
  }
}
?>
<table id="objectGrid" jsId="objectGrid" dojoType="dojox.grid.DataGrid"
  query="{ id: '*' }" store="objectStore"
  queryOptions="{ignoreCase:true}"
  rowPerPage="<?php echo Parameter::getGlobalParameter('paramRowPerPage');?>"
  <?php
    if ($savedSort) {
      $descending = ($savedSort['order'] == 'desc') ? 'true' : 'false';
      echo 'sortFields="[{attribute:\'' . htmlspecialchars($savedSort['field']) . '\',descending:' . $descending . '}]"';
    }
  ?>
  <?php if($comboDetail){?>
    columnReordering="false"
  <?php }else{?>
    columnReordering="true"
  <?php }?> 
  rowSelector="false"
  loadingMessage="loading"
  noDataMessage="no data to display"
  fastScroll="false"
  onHeaderClick="unselectAllRows('objectGrid');selectGridRow();saveGridSortOnClick();"
  onHeaderCellContextMenu="dijit.byId('listColumnSelector').toggleDropDown();"
  selectionMode="<?php echo ($multipleSelect)?'extended':'single';?>" >
  <thead>
    <tr>
      <?php echo $obj->getLayout();?>
    </tr>
  </thead>
<script type="dojo/method" event="startup">
  var grid = this;
  <?php if ($savedSort) { ?>
  var fieldName = '<?php echo $savedSort['field']; ?>';
  var descending = <?php echo ($savedSort['order'] == 'desc') ? 'true' : 'false'; ?>;
  setTimeout(function() {
    var cells = grid.layout.cells;
    var columnIndex = -1;
    for (var i = 0; i < cells.length; i++) {
      if (cells[i] && cells[i].field === fieldName) {
        columnIndex = i + 1; 
        break;
      }
    }
    grid.setSortIndex(fieldName, descending);
    if (columnIndex > 0) {
      grid.sortInfo = descending ? -columnIndex : columnIndex;
    }
    setTimeout(function() {
      var headers = dojo.query('th[role="columnheader"]', grid.domNode);
      columnIndex = -1;
      for (var i = 0; i < cells.length; i++) {
        if (cells[i] && cells[i].field === fieldName) {
          columnIndex = i;
          break;
        }
      }
      if (columnIndex >= 0 && columnIndex < headers.length) {
        var headerNode = headers[columnIndex];
        headers.forEach(function(node) {
          dojo.removeClass(node, 'dojoxGridSorted');
          node.setAttribute('aria-sort', 'none');
        });
        dojo.addClass(headerNode, 'dojoxGridSorted');
        headerNode.setAttribute('aria-sort', descending ? 'descending' : 'ascending'); 
        var sortNode = dojo.query('.dojoxGridSortNode', headerNode)[0];
        if (sortNode) {
          var columnText = cells[columnIndex].name || fieldName;
          sortNode.innerHTML = 
            '<div class="dojoxGridArrowButtonChar">' + (descending ? '▼' : '▲') + '</div>' +
            '<div class="dojoxGridArrowButtonNode" role="presentation"></div>' +
            '<div class="dojoxGridColCaption">' + columnText + '</div>';  
          dojo.removeClass(sortNode, 'dojoxGridSortUp');
          dojo.removeClass(sortNode, 'dojoxGridSortDown');
          dojo.addClass(sortNode, descending ? 'dojoxGridSortDown' : 'dojoxGridSortUp');
        }
      }
      if (isNaN(grid.sortInfo) && columnIndex >= 0) {
        grid.sortInfo = descending ? -(columnIndex + 1) : (columnIndex + 1);
      }
      
    }, 200);
  }, 300);
  <?php } ?>
  dojo.connect(grid, 'onSort', function() {
    var sortInfo = grid.getSortProps();
    if (sortInfo && sortInfo.length > 0) {
      var sort = sortInfo[0];
      saveGridSort('<?php echo $objectClass; ?>', sort.attribute, sort.descending);
    }
  });
</script>
  <script type="dojo/connect" event="onRowContextMenu" args="e">
    var rowIndex = e.rowIndex; //Keep
    if (typeof historyTable == 'undefined') return;
    var rowItem = dijit.byId('objectGrid').get('_by_idx')[rowIndex];
    var id = rowItem.idty;
    var obj = dojo.byId('objectClass').value;
    if (obj === 'GlobalView'){
      var className = id.replace(/\d+/g, '');
      var objectId = id.replace(/\D+/g, '');
    }else{
      var hasLetters = /[a-zA-Z]/.test(id);
      var hasDigits = /\d/.test(id);
      if (hasLetters && hasDigits){
        var className = id.replace(/\d+/g, '');
        var objectId = id.replace(/\D+/g, '');
      }else{
        var className = obj;
        var objectId = parseInt(rowItem.idty,10);
      }
    }
    dojo.byId('objectClassRow').value = className;
    dojo.byId('objectIdRow').value = objectId;

    var contextMenu = dijit.byId('objectContextMenu');
    var contextMenuDiv = dojo.byId('dialogObjectContextMenu');
    var mousePosition = {};
    mousePosition.x = event.clientX;
      if(dojo.byId('isMenuLeftOpen').value == 'true'){
      mousePosition.x -= 250;
    }
    var posX=110;
    if (dojo.byId("barFilterByTags") && dojo.byId("barFilterByTags").style.display=='block') posX+=dojo.byId("barFilterByTags").offsetHeight;
    if (dojo.byId("barFilterByStatus") && dojo.byId("barFilterByStatus").style.display=='block') posX+=dojo.byId("barFilterByStatus").offsetHeight; 
    mousePosition.y = event.clientY-posX;
    dojo.query('.contextMenuClass').forEach(function(node){
      node.style.cssText='position:absolute;width:0px;height:0px;overflow:hidden;top:'+mousePosition.y+'px;left:'+mousePosition.x+'px';
    });
    if(dojo.byId('copyFromObject')){
      dojo.byId('copyFromObject').style.display = '';
      // dojo.byId('copyFromObject').setAttribute('onClick', 'copyObjectFromContextMenu(\''+objectId+'\', \''+className+'\', null, null, true);loadContent("objectDetail.php", "detailDiv", "listForm")');
      // if loadContent in copyObjectBox ckEditorReplaceEditor doesn't work.
      dojo.byId('copyFromObject').setAttribute('onClick', 'copyObjectFromContextMenu(\''+objectId+'\', \''+className+'\', null, null, true);');
    }
    if(dojo.byId('removeFromObject')){
      dojo.byId('removeFromObject').style.display = '';
      dojo.byId('removeFromObject').setAttribute('onClick', 'deleteObjectFromContextMenu(\''+objectId+'\', \''+className+'\', true)');
    } 
    if(dojo.byId('printFromObject')){
      dojo.byId('printFromObject').style.display = '';
      dojo.byId('printFromObject').setAttribute('onClick', 'showPrint(\'objectDetail.php\', \'contextMenuObject\', null, null, \'P\')');
    }   
    if(dojo.byId('printPdfFromObject')){
      dojo.byId('printPdfFromObject').style.display = '';
      dojo.byId('printPdfFromObject').setAttribute('onClick', 'showPrint(\'objectDetail.php\', \'contextMenuObject\', null, \'pdf\', \'P\')');
    }
    if(dojo.byId('mailFromObject')){
      dojo.byId('mailFromObject').style.display = '';
      dojo.byId('mailFromObject').setAttribute('onClick', 'showMail()');
    }
    if(dojo.byId('searchFromObject')){
      dojo.byId('searchFromObject').style.display = '';
      if(0 && className === 'Project'){ // PBER #10182
        dojo.byId('searchFromObject').setAttribute('onClick', 'noRefresh=true;gotoElement(\''+className+'\', \''+objectId+'\' ,false, false,\'planning\',false)');
      }else{
        dojo.byId('searchFromObject').setAttribute('onClick','directSelectProject(\''+className+'\', \''+objectId+'\' ,true, true)');
      }
    }

    if(dojo.byId('selectFromObject')){
      dojo.byId('selectFromObject').style.display = '';
      dojo.byId('selectFromObject').setAttribute('onClick', 'directSelectProject("'+className+'",'+objectId+',true)');
    }
    dojo.xhrGet({
      url:'../tool/getSingleData.php?dataType=canSearchObject&objectClass='+className+'&objectId='+objectId+addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
        if(! data || data=='0'){
          dojo.byId('searchFromObject').style.display = 'none';
        }  
      }
    });
    if(dojo.byId('addFromObject')){
      dojo.byId('addFromObject').style.display = '';
      if (objectId) { 	
        var currentItem = (historyPosition >= 0) ? historyTable[historyPosition] : null;
        var currentScreen = (currentItem && currentItem.length > 2) ? currentItem[2] : null;
        if (currentItem && currentItem[0] == currentScreen && dojo.byId("objectId")) return;
        if (currentItem && (currentScreen == "Planning" || currentScreen == "GlobalPlanning") || ((currentScreen == "VersionsPlanning" || currentScreen == "ResourcePlanning") && objectClass == "Activity")) {
          var currentItemParent=(currentItem[1]!=null)?currentItem[1]:objectId;
          var originClass=(currentItem[0] && currentScreen != "Planning" && currentScreen != "GlobalPlanning" && currentScreen != "VersionsPlanning" && currentScreen != "ResourcePlanning")?currentItem[0]:objectClass;
          var url = 'objectDetail.php?insertItem=true&currentItemParent=' + currentItemParent + '&originClass=' + originClass + '&planningType=' + dojo.byId("objectClassManual").value;
          if (currentScreen == "VersionsPlanning" || currentScreen == "ResourcePlanning") {
            url += "&currentPlanning=" + currentScreen;
          } 
          objectId = "";
          dojo.byId('addFromObject').setAttribute('onClick', 'unselectAllRows("objectGrid");loadContent(url, "detailDiv", "listForm");');     
          } else if ((currentScreen == "VersionsPlanning" || currentScreen == "ResourcePlanning") && objectClass != "Activity") {
            dojo.byId('addFromObject').setAttribute('onClick', 'showAlert(i18n("alertActivityVersion"));');  
          } else {
            objectId = "";
            dojo.byId('objectId').value="";
            dojo.byId('addFromObject').setAttribute('onClick', 'unselectAllRows("objectGrid");loadContent("objectDetail.php", "detailDiv", "listForm");loadContentStream();');  
          }
        } else {
            dojo.byId('addFromObject').setAttribute('onClick', 'showError(i18n("errorObjectId"));'); 
        }
    }
    objectGrid.selection.clear();
    contextMenu.openDropDown();
    contextMenuDiv.focus();
  </script>
  <script type="dojo/connect" event="onSelected" args="evt">
    if (gridReposition) {return;}
    if (multiSelection) {updateSelectedCountMultiple();return;} 
	  if ( dojo.byId('comboDetail') ) {
      rows=objectGrid.selection.getSelected();
      row=rows[0]; 
      dojo.byId('comboDetailId').value=row.id;
      dojo.byId('comboDetailId').value=dojo.byId('comboDetailId').value.replace(/^[0]+/g,"");
      dojo.byId('comboDetailName').value=row.name;
      return true;
    }
    var ctrlPressed=(window.event && (window.event.ctrlKey || window.event.shiftKey))?true:false;
    if (!multiSelection && ctrlPressed) {
      rows=objectGrid.selection.getSelected();
      row=rows[0]; 
      refId = row.id;
<?php if (get_class($obj)=='GlobalView') {?>
      classNameCol=row.objectClass+"";
      className=classNameCol.split('|');
      refType=className[1];
<?php } else {?>
      refType=dojo.byId('objectClass').value;
<?php }?>
      openInNewWindow(refType, refId);
      selectRowById('objectGrid', parseInt(dojo.byId('objectId').value));
      return false;
    }
    actionYes = function () {
      rows=objectGrid.selection.getSelected();
      row=rows[0]; 
      var id = row.id;
	  dojo.byId('objectId').value=id;
  <?php if (get_class($obj)=='GlobalView') {?>
        dojo.byId('objectId').value=row.objectId;
        classNameCol=row.objectClass+"";
        className=classNameCol.split('|');
        dojo.byId('objectClass').value=className[1];
  <?php }?>
	  //cleanContent("detailDiv");
      formChangeInProgress=false; 
      listClick();
      loadContent("objectDetail.php", "detailDiv", 'listForm');
      loadContentStream();

    }
    actionYesSave = function () {
      rows=objectGrid.selection.getSelected();
      row=rows[0]; 
      var id = row.id;
	  dojo.byId('objectId').value=id;
      formChangeInProgress=false;
      var actionRefresh = function(){
        noRefreshAfterSave = false;
      };
      loadContent("objectDetail.php", "detailDiv", 'listForm', null, null, null, actionRefresh);
      loadContentStream();

    }
    actionSave = function () {
      noRefreshAfterSave = true;
      saveObject(actionYesSave);

   	}
    actionNo = function () {
	    //unselectAllRows("objectGrid");
      selectRowById('objectGrid', parseInt(dojo.byId('objectId').value));
    }
    if (checkFormChangeInProgress(actionYes, actionNo, actionSave)) {
      return true;
    }

  </script>
  <script type="dojo/connect" event="onDeselected" args="evt">
    if (multiSelection) {updateSelectedCountMultiple();return;}
  </script>
  <script type="dojo/method" event="onRowDblClick" args="row">
    if ( dojo.byId('comboDetail') ) {
      rows=objectGrid.selection.getSelected();
      row=rows[0]; 
      dojo.byId('comboDetailId').value=row.id;
      dojo.byId('comboDetailId').value=dojo.byId('comboDetailId').value.replace(/^[0]+/g,"");
      dojo.byId('comboDetailName').value=row.name;
      window.top.selectDetailItem();
      return;
    }
  </script>
  <script type="dojo/connect" event="onMoveColumn" args="evt">
    var colLayout = objectGrid.rows.grid.layout.cells;
    var jsonValue = "";
    colLayout.forEach(function(currentValue) {
      jsonValue = jsonValue+currentValue.field+"__";
    });
    dojo.xhrGet({
    url: '../tool/saveMoveColumn.php?class=<?php echo get_class($obj);?>&mode=move&jsonValue='+jsonValue+addTokenIndexToUrl(),
    load: function(data,args) { 
    
    }
  });
  </script>
  <script type="dojo/connect" event="onResizeColumn" args="colIdx">
 <?php if(!$comboDetail){?>
    var colLayout = objectGrid.rows.grid.layout.cells;
    var totalDiv = dojo.byId("objectGrid").offsetWidth;
    var jsonValue = "";
    var lastChar = "";
    colLayout.forEach(function(currentValue) {
      jsonValue = jsonValue+currentValue.unitWidth+"__";
      var char = currentValue.unitWidth;
     lastChar = char.substr(char.length - 2);
    });
    var callBack = function(){
    dojo.xhrGet({
    url: '../tool/saveMoveColumn.php?class=<?php echo get_class($obj);?>&totalDiv='+totalDiv+'&mode=size&jsonValue='+jsonValue+addTokenIndexToUrl(),
    load: function(data,args) {
    if(data){
      arrayData=data.split('#!#!#!#!#!#');
      objectGrid.setCellWidth(arrayData[0], arrayData[1]);
      dojo.forEach(grid.layout.cells, function(cell,idx){
        if(idx==arrayData[0]){
            grid.setCellWidth(idx, arrayData[1]);
            cell.view.update(); 
          }
        });
    objectGrid.update();
    }
    }
  });
  }
  if(lastChar=='px'){
    callBack();
  }      
 <?php } ?>
  </script>
  <script type="dojo/connect" event="_onFetchComplete" args="items, req">
     if (mustApplyFilter) {
       mustApplyFilter=false;
       filterJsonList(dojo.byId('objectClass').value);
     } else {
       refreshGridCount();
     }
     //setTimeout('dijit.byId("objectGrid").resize();',10); // PBER #2733 - Commented as it blocks scrolling in the grid - This line was added in V8.2.X, but cannot identify why
     runRefreshListAuto();
  </script>
</table>
</div>
</div>
<?php 
function organizeListButtons($nbButton=1) {
  //return;
  global $cptListButton,$extendedListZone;
  $cptListButton+=$nbButton;
  if ( isNewGui()) {
    if (! $extendedListZone) {
      echo "<! ========================================================>";
      $extendedListZone=true;
      echo '<td class="allSearchFixLength">';
      echo '<div style="position:relative;z-index:9">';
      echo '<div dojoType="dijit.form.Button" showlabel="false" title="'. i18n('extraButtonsBar'). '" '
          .' iconClass="dijitButtonIcon dijitButtonIconExtraButtons" class="detailButton" '
          .' id="extraButtonsList" onClick="showExtraButtons(\'extraButtonsList\')" '
          .'></div>';
      echo '<div class="statusBar" id="extraButtonsListDiv" style="display:none;">';
      echo '<table><tr>';
    } else {
      echo '</tr><tr>';
    }
  }
}

function organizeListButtonsEnd() {
  //return;
  global $extendedListZone;
  if ($extendedListZone) {
    echo "<! ========================================================>";
    echo '</tr></table></div></div></td>';
  }
}
?>
