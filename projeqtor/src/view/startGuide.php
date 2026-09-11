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
 * List of parameter specific to a user.
 * Every user may change these parameters (for his own user only !).
 */
require_once "../tool/projeqtor.php";
require_once "../tool/projeqtor.php";
scriptLog('   ->/view/startGuide.php');  
$user=getSessionUser();

if(isNewGui()){
  $progress=0;
  $total=0;
  
  $lastTab = Parameter::getUserParameter('startGuideTab');
  if(!pq_trim($lastTab)){
    $lastTab = 'startGuideEnvironmentalTab';
  }
  
  $limitRow = 100;
  
  echo '<div class="container" >';
  echo '<input type="hidden" name="objectClassManual" id="objectClassManual" value="StartGuide" />';
   echo '<div class="backgroundToday" style="width:100%; height:100%;position:absolute;opacity:0.3 !important;z-index:-2">&nbsp;</div>';
   echo '<div class="backgroundToday" style="width:250%; height:250%;position:absolute;opacity:0.05 !important;top:-50%;z-index:-2">&nbsp;</div>';
   echo '<div style="height:100%;padding:2%;position:relative;overflow:auto;">';
     echo '<div class="simple-grid-top" style="width:100%;height:100px">'.i18n('startGuideTitle').'</div>';
     echo '<div style="width:100%;padding-bottom: 20px;">'.i18n('startGuideIntro').'</div>';
     echo '<div id="startGuideTabContainer" data-dojo-type="dijit/layout/TabContainer" style="width: 100%;Height:600px" doLayout="true">';
       echo '<div id="startGuideEnvironmentalTab" class="transparentBackground" data-dojo-type="dijit/layout/ContentPane"';
       
//        $arrayItem=array('Client','Contact', 'Resource', 'User');
//        $validatedItem=array();
//        foreach ($arrayItem as $item) {
//          $obj=new $item();
//          $where = '1=1';
//          if ($item=='Contact' or $item=='Resource' or $item=='User') {
//            $where = 'is'.pq_strtolower($item).'=1';
//          }
//          $nbItem=$obj->countSqlElementsFromCriteria(null,$where);
//          if ($nbItem==0 or ($item=='User' and $nbItem<=2) ) {
//            if(isset($validatedItem[$item]))unset($validatedItem[$item]);
//          } else {
//            $validatedItem[$item]=true;
//          }
//        }
//        $badgeTab = '<img src=\'css/images/iconStartGuideTodo.png\' />';
//        if(count($validatedItem) == count($arrayItem)){
//          $badgeTab = '<img src=\'css/images/iconStartGuideDone.png\' />';
//        }
       $badgeTab='';
       
       echo 'title="'.i18n('stakeholders').'<div id=\'startGuideEnvironmentalTabBadge\' class=\'startGuideFirstTabBadge\' >'.$badgeTab.'</div>"';
       echo 'style="overflow: hidden;" data-dojo-props="'.(($lastTab == 'startGuideEnvironmentalTab')?'selected:true':'').'">';
       echo '<script type="dojo/connect" event="onShow" args="evt">
              dijit.byId(\'startGuideTabContainer\').watch("selectedChildWidget", function(name, oldValue, newValue) {
                saveDataToSession(\'startGuideTab\', newValue.id,true);
              });
            </script>';
       echo '<div class="siteH2" align="left" style="width:100%;padding:25px 0px 10px 10px;color:#656565 !important"><b>'.i18n("startGuideActionMenu").' "'.i18n('stakeholders').'"</b></div>';
       echo '<div class="simple-grid">';
          $arrayItem=array('Client','Contact', 'Resource', 'User');
          $order = 1;
          foreach ($arrayItem as $item) {
            $total++;
            $hideAutoloadError=true; // Avoid error message is autoload
            $is_object=SqlElement::class_exists($item,true);
            $hideAutoloadError=false;
            $canRead=(securityGetAccessRightYesNo('menuUser', 'read') == "YES");
            echo '<div id="show'.$item.'Tab" class="simple-grid__cell simple-grid__cell--1-4" style="order:'.$order.'">';
              echo '<div class="simple-grid__header"></div>';
              echo '<div class="simple-grid__container">';
                echo '<table style="width:100%;height:100%"><tr>';
                $obj=new $item();
                $where = '1=1';
                if ($item=='Contact' or $item=='Resource' or $item=='User') {
                  $where = 'is'.pq_strtolower($item).'=1';
                }
                $nbItem=$obj->countSqlElementsFromCriteria(null,$where);
                $listItem=$obj->getSqlElementsFromCriteria(null,null,$where,null,false,null,$limitRow);
                $title = i18n('menu'.$item);
                if ($nbItem==0 or ($item=='User' and $nbItem<=2) ) {
                 $countColor = 'lightgrey';
                } else {
                 $countColor = 'green';
                 $progress++;
                }
                echo '  <td title="'.$title.'" style="width:32px;height:32px;"><div style="border-radius:3px;background-color:'.$countColor.';color:white;text-align:center;">';
                echo '    <div style="line-height: 32px;font-size:15px;font-weight:bold">'.$nbItem.'</div>';
                echo '  </div></td>';
                echo '  <td class="simple-grid__header" style="padding: unset;">';
                echo '    <div style="text-align:left;padding-left:15px;cursor:pointer;" onClick="loadMenuBar'.(($is_object)?'Object':'Item').'(\'' . $item .  '\',null,\'bar\');">'.i18n('menu'.$item).'</div></td>';
                
                echo '  <td title="'.i18n('sectionHelp').'" style="width:32px;height:32px;">';
                echo '    <div class="imageColorNewGui iconHelpMenuStartGuide iconSize22" id="'.$item.'" style="cursor:pointer; margin-left:10px;" onclick="showHelp(\''.$item.'\');"></div></td>';
                
                echo '  </tr>';
                
                $help=i18n("startGuide".$item);
                if (pq_substr($help,0,1)!='[') {
                  i18n("startGuide".$item);
                }
                echo '<tr><td style="padding:10px 0px 10px;font-size:12px;font-style: italic;" colspan="3">';
                if($nbItem > 0){
                  echo '<div style="width:100%;height:75px;overflow-y:auto;">'.$help.'</div>';
                  echo '</td></tr>';
                  echo '<tr><td colspan="3"><div style="width:100%;height:250px;overflow-y:auto;overflow-x: hidden;border-radius:15px;border: 1px solid #CCCCCC">';
                  echo '<table style="margin:15px;width: 100%;color:#AAAAAA">';
                  foreach ($listItem as $id=>$obj){
                    $name = '';
                    if(property_exists(get_class($obj), 'name')){
                      $name = '#'.$obj->id.' '.$obj->name;
                    }else if(property_exists(get_class($obj), 'refType') && property_exists(get_class($obj), 'refId')){
                      $name = '#'.$obj->refId.' '.$obj->refType;
                    }
                    $canGoto=(securityCheckDisplayMenu(null, get_class($obj)) and securityGetAccessRightYesNo('menu'.get_class($obj), 'read', $obj)=="YES")?true:false;
                    $gotoItem = '';
                    if($canGoto){
                      $gotoItem = 'onClick="gotoElement('."'".get_class($obj)."','".htmlEncode($obj->id)."'".');"';
                    }
                    echo '<tr class="startGuideListRow" '.$gotoItem.'><td style="width:95%;padding-bottom:10px;text-overflow:ellipsis;cursor:pointer">'.$name.'</td><td style="width:5%;padding-bottom:10px;padding-right:30px">'.formatSmallButton('Goto', true).'</td><tr>';
                  }
                  if($nbItem >= $limitRow){
                    echo '<tr class="startGuideListRow"><td colspan="3" style="padding-top: 10px;"><div style="text-align:center;margin-right: 10%;background: #FFDDDD;color: #808080;border-radius: 5px;padding: 2px;">'.i18n('limitedDisplay', array($limitRow)).'</div></td><tr>';
                  }
                  echo '</table>';
                }else{
                  echo '<div style="width:100%;height:120px;overflow-y:auto;">'.$help.'</div>';
                  echo '</td></tr>';
                  echo '<tr><td colspan="3"><div style="width:100%;min-height:205px;max-height:250px;overflow-y:auto;overflow-x: hidden;border-radius:15px;border: 1px solid #CCCCCC">';
                  echo '<table style="margin:10px;width: 95%;min-height:185px;max-height:230px;"><tr>';
                  echo '  <td align="'.(($item != 'User' and $item != 'Resource')?'right':'center').'" style="padding-right:5px;">';
                  echo '    <div onClick="loadMenuBar'.(($is_object)?'Object':'Item').'(\'' . $item .  '\',null,\'bar\');">';
                  echo '    <span class="roundedButtonSmall" style="top:0px;display:inline-block;width:64px;height:64px;"><div class="iconButtonAdd imageColorNewGui" style="background-repeat:no-repeat;width:64px;height:64px;background-size:64px 64px">&nbsp;</div></span>';
                  echo '</div></td>';
                  if($item != 'User' and $item != 'Resource'){
                    echo '  <td align="left" style="padding-leftp:5px">';
                    echo '    <div onClick="gotoImportData(\''.$item.'\');">';
                    echo '    <span class="roundedButtonSmall" style="top:0px;display:inline-block;width:64px;height:64px;"><div class="iconButtonUpload imageColorNewGui" style="background-repeat:no-repeat;width:64px;height:64px;background-size:64px 64px">&nbsp;</div></span>';
                    echo '  </div></td>';
                  }
                  echo '</tr></table>';
                }
                echo '</div></td></tr>';
                echo '<tr>';
                echo '  <td align="center" style="padding-top:10px" colspan="3">';
                echo '    <table><tr>';
                if($canRead and $nbItem > 0){
                  echo '      <td align="'.(($item != 'User' and $item != 'Resource')?'right':'center').'" style="padding-right:5px;">';
                  echo '        <div onClick="loadMenuBar'.(($is_object)?'Object':'Item').'(\'' . $item .  '\',null,\'bar\');">'.formatBigButton('Add').'</div></td>';
                  if($item != 'User' and $item != 'Resource'){
                    echo '      <td align="left" style="padding-leftp:5px">';
                    echo '        <div onClick="gotoImportData(\''.$item.'\');">'.formatBigButton('Upload').'</div></td>';
                  }
                }else{
                  echo '      <td align="right" style="height:32px"></td>';
                  echo '      <td align="left" style="height:32px"></td>';
                }
                echo '    </tr></table>';
                echo '  </td>';
                echo '</tr>';
                echo '</table>';
              echo '</div>';
            echo '</div>';
            $order++;
          }
        echo '</div>';
       echo '</div>';
       echo '<div id="startGuidePlanningTab" class="transparentBackground" data-dojo-type="dijit/layout/ContentPane"';
       
//        $arrayItem=array('Project', 'Affectation', 'Activity', 'Milestone');
//        $validatedItem=array();
//        foreach ($arrayItem as $item) {
//          $obj=new $item();
//          $where = '1=1';
//          if ($item=='Project') {
//            $where = 'isLeaveMngProject = 0';
//          }
//          $nbItem=$obj->countSqlElementsFromCriteria(null,$where);
//          if ($nbItem==0) {
//            if(isset($validatedItem[$item]))unset($validatedItem[$item]);
//          } else {
//            $validatedItem[$item]=true;
//          }
//        }
//        $badgeTab = '<img src=\'css/images/iconStartGuideTodo.png\' />';
//        if(count($validatedItem) == count($arrayItem)){
//          $badgeTab = '<img src=\'css/images/iconStartGuideDone.png\' />';
//        }
       $badgeTab='';
       
       echo 'title="'.i18n('modulePlanning').'<div id=\'startGuidePlanningTabBadge\' class=\'startGuideTabBadge\' >'.$badgeTab.'</div>" ';
       echo 'style="overflow: hidden;" data-dojo-props="'.(($lastTab == 'startGuidePlanningTab')?'selected:true':'').'">';
       echo '<script type="dojo/connect" event="onShow" args="evt">
              dijit.byId(\'startGuideTabContainer\').watch("selectedChildWidget", function(name, oldValue, newValue) {
                saveDataToSession(\'startGuideTab\', newValue.id,true);
              });
            </script>';
       echo '<div class="siteH2" align="left" style="width:100%;padding:25px 0px 10px 10px;color:#656565 !important"><b>'.i18n("startGuideActionMenu").' "'.i18n('modulePlanning').'"</b></div>';
        echo '<div class="simple-grid">';
         $arrayItem=array('Project', 'Affectation', 'Activity', 'Milestone');
         $order = 1;
         foreach ($arrayItem as $item) {
           $total++;
           $hideAutoloadError=true; // Avoid error message is autoload
           $is_object=SqlElement::class_exists($item,true);
           $hideAutoloadError=false;
           $canRead=(securityGetAccessRightYesNo('menuUser', 'read') == "YES");
           echo '<div id="show'.$item.'Tab" class="simple-grid__cell simple-grid__cell--1-4" style="order:'.$order.'">';
             echo '<div class="simple-grid__header"></div>';
              echo '<div class="simple-grid__container">';
                echo '<table style="width:100%"><tr>';
                $obj=new $item();
                $where = '1=1';
                if ($item=='Project') {
                  $where = 'isLeaveMngProject = 0';
                }
                $nbItem=$obj->countSqlElementsFromCriteria(null,$where);
                $listItem=$obj->getSqlElementsFromCriteria(null,null,$where,null,false,null,$limitRow);
                $title = i18n('menu'.$item);
                if ($nbItem==0 or ($item=='User' and $nbItem<=2) ) {
                 $countColor = 'lightgrey';
                } else {
                 $countColor = 'green';
                 $progress++;
                }
                echo '  <td title="'.$title.'" style="width:32px;height:32px;"><div style="border-radius:3px;background-color:'.$countColor.';color:white;text-align:center;">';
                echo '    <div style="line-height: 32px;font-size:15px;font-weight:bold">'.$nbItem.'</div>';
                echo '  </div></td>';
                echo '  <td class="simple-grid__header" style="padding: unset;">';
                echo '    <div style="text-align:left;padding-left:15px;cursor:pointer;" onClick="loadMenuBar'.(($is_object)?'Object':'Item').'(\'' . $item .  '\',null,\'bar\');">'.i18n('menu'.$item).'</div>';
                echo '  </td>';
                
                echo '  <td title="'.i18n('sectionHelp').'" style="width:32px;height:32px;">';
                echo '    <div class="imageColorNewGui iconHelpMenuStartGuide iconSize22" id="'.$item.'" style="cursor:pointer; margin-left:10px;" onclick="showHelp(\''.$item.'\');"></div></td>';
                
                echo '  </tr>';
                $help=i18n("startGuide".$item);
                if (pq_substr($help,0,1)!='[') {
                  i18n("startGuide".$item);
                }
                echo '<tr><td style="padding:10px 0px 10px;font-size:12px;font-style: italic;" colspan="3">';
                if($nbItem > 0){
                  echo '<div style="width:100%;height:75px;overflow-y:auto;">'.$help.'</div>';
                  echo '</td></tr>';
                  echo '<tr><td colspan="3"><div style="width:100%;height:250px;overflow-y:auto;overflow-x: hidden;border-radius:15px;border: 1px solid #CCCCCC">';
                  echo '<table style="margin:15px;width: 100%;color:#AAAAAA">';
                  foreach ($listItem as $id=>$obj){
                    $name = '';
                    if(property_exists(get_class($obj), 'name')){
                      $name = '#'.$obj->id.' '.$obj->name;
                    }else if(property_exists(get_class($obj), 'refType') && property_exists(get_class($obj), 'refId')){
                      $name = '#'.$obj->refId.' '.$obj->refType;
                    }
                    if($item=='Affectation'){
                      $name = '#'.$obj->idProject.' '.SqlList::getNameFromId('Project', $obj->idProject).' - #'.$obj->idResource.' '.SqlList::getNameFromId('ResourceAll', $obj->idResource);
                    }
                    $canGoto=(securityCheckDisplayMenu(null, get_class($obj)) and securityGetAccessRightYesNo('menu'.get_class($obj), 'read', $obj)=="YES")?true:false;
                    $gotoItem = '';
                    if($canGoto){
                      $gotoItem = 'onClick="gotoElement('."'".get_class($obj)."','".htmlEncode($obj->id)."'".');"';
                    }
                    echo '<tr class="startGuideListRow" '.$gotoItem.'><td style="width:95%;padding-bottom:10px;text-overflow:ellipsis;cursor:pointer">'.$name.'</td><td style="width:5%;padding-bottom:10px;padding-right:30px;">'.formatSmallButton('Goto', true).'</td><tr>';
                  }
                  if($nbItem >= $limitRow){
                    echo '<tr class="startGuideListRow"><td colspan="3" style="padding-top: 10px;"><div style="text-align:center;margin-right: 10%;background: #FFDDDD;color: #808080;border-radius: 5px;padding: 2px;">'.i18n('limitedDisplay', array($limitRow)).'</div></td><tr>';
                  }
                  echo '</table>';
                }else{
                  echo '<div style="width:100%;height:120px;overflow-y:auto;">'.$help.'</div>';
                  echo '</td></tr>';
                  echo '<tr><td colspan="3"><div style="width:100%;min-height:205px;max-height:250px;overflow-y:auto;overflow-x: hidden;border-radius:15px;border: 1px solid #CCCCCC">';
                  echo '<table style="margin:10px;width: 95%;min-height:185px;max-height:230px;"><tr>';
                  echo '  <td align="'.(($item == 'Affectation')?'right':'center').'" style="padding-right:5px;">';
                  echo '    <div onClick="loadMenuBar'.(($is_object)?'Object':'Item').'(\'' . $item .  '\',null,\'bar\');">';
                  echo '    <span class="roundedButtonSmall" style="top:0px;display:inline-block;width:64px;height:64px;"><div class="iconButtonAdd imageColorNewGui" style="background-repeat:no-repeat;width:64px;height:64px;background-size:64px 64px">&nbsp;</div></span>';
                  echo '  </div></td>';
                  if($item == 'Affectation'){
                    echo '  <td align="left" style="padding-leftp:5px">';
                    echo '    <div onClick="gotoImportData(\''.$item.'\');">';
                    echo '    <span class="roundedButtonSmall" style="top:0px;display:inline-block;width:64px;height:64px;"><div class="iconButtonUpload imageColorNewGui" style="background-repeat:no-repeat;width:64px;height:64px;background-size:64px 64px">&nbsp;</div></span>';
                    echo '  </div></td>';
                  }
                  echo '</tr></table>';
                }
                echo '</div></td></tr>';
                echo '<tr>';
                echo '  <td align="center" style="padding-top:10px" colspan="3">';
                echo '    <table><tr>';
                if($canRead and $nbItem > 0){
                  echo '      <td align="'.(($item == 'Affectation')?'right':'center').'" style="padding-right:5px;">';
                  echo '        <div onClick="loadMenuBar'.(($is_object)?'Object':'Item').'(\'' . $item .  '\',null,\'bar\');">'.formatBigButton('Add').'</div></td>';
                  if($item == 'Affectation'){
                    echo '      <td align="left" style="padding-leftp:5px">';
                    echo '        <div onClick="gotoImportData(\''.$item.'\');">'.formatBigButton('Upload').'</div></td>';
                  }
                }else{
                  echo '      <td align="center" style="height:32px"></td>';
                }
                echo '    </tr></table>';
                echo '  </td>';
                echo '</tr>';
                echo '</table>';
              echo '</div>';
           echo '</div>';
           $order++;
         }
         echo '</div>';
       echo '</div>';
       echo '<div id="startGuideFollowUpTab" class="transparentBackground" data-dojo-type="dijit/layout/ContentPane"';
       
//        $arrayItem=array('Planning','Imputation','Ticket');
//        $validatedItem=array();
//        foreach ($arrayItem as $item) {
//          if ($item=='Planning') {
//            $obj=new PlannedWork();
//            $nbItem=0;
//            $nb=$obj->countGroupedSqlElementsFromCriteria(array(), array('idProject'), "1=1");
//            if ($nb) {
//              $nbItem=count($nb);
//            }
//          } else if ($item=='Imputation') {
//            $obj=new PlannedWork();
//            $nbItem=0;
//            $nb=$obj->countGroupedSqlElementsFromCriteria(array(), array('idResource'), "1=1");
//            if ($nb) {
//              $nbItem=count($nb);
//            }
//          } else {
//             $obj=new $item();
//             $where = "1=1";
//             $nbItem=$obj->countSqlElementsFromCriteria(null,$where);
//          }
//          if ($nbItem==0) {
//            if(isset($validatedItem[$item]))unset($validatedItem[$item]);
//          } else {
//            $validatedItem[$item]=true;
//          }
//        }
//        $badgeTab = '<img src=\'css/images/iconStartGuideTodo.png\' />';
//        if(count($validatedItem) == count($arrayItem)){
//          $badgeTab = '<img src=\'css/images/iconStartGuideDone.png\' />';
//        }
       $badgeTab = '';
       
       echo 'title="'.i18n('moduleFollowUp').'<div id=\'startGuideFollowUpTabBadge\' class=\'startGuideTabBadge\' >'.$badgeTab.'</div>"';
       echo 'style="overflow: hidden;" data-dojo-props="'.(($lastTab == 'startGuideFollowUpTab')?'selected:true':'').'">';
       echo '<script type="dojo/connect" event="onShow" args="evt">
              dijit.byId(\'startGuideTabContainer\').watch("selectedChildWidget", function(name, oldValue, newValue) {
                saveDataToSession(\'startGuideTab\', newValue.id,true);
              });
            </script>';
       echo '<div class="siteH2" align="left" style="width:100%;padding:25px 0px 10px 10px;color:#656565 !important"><b>'.i18n("startGuideActionMenu").' "'.i18n('moduleFollowUp').'"</b></div>';
        echo '<div class="simple-grid transparent">';
         $arrayItem=array('Planning','Imputation','Ticket');
         $order = 1;
         foreach ($arrayItem as $item) {
           $total++;
           $hideAutoloadError=true; // Avoid error message is autoload
           $is_object=SqlElement::class_exists($item,true);
           $hideAutoloadError=false;
           $canRead=(securityGetAccessRightYesNo('menuUser', 'read') == "YES");
           echo '<div id="show'.$item.'Tab" class="simple-grid__cell simple-grid__cell--1-4" style="order:'.$order.'">';
            echo '<div class="simple-grid__header"></div>';
              echo '<div class="simple-grid__container">';
                echo '<table style="width:100%"><tr>';
                $title = i18n('menu'.$item);
                if ($item=='Planning') {
                   $title = i18n('plannedProjects');
                   $obj=new PlannedWork();
                   $nbItem=0;
                   $nb=$obj->countGroupedSqlElementsFromCriteria(array(), array('idProject'), "1=1");
                   if ($nb) {
                     $nbItem=count($nb);
                   }
                   $listItem=$nb;
                } else if ($item=='Imputation') {
                   $obj=new PlannedWork();
                   $nbItem=0;
                   $nb=$obj->countGroupedSqlElementsFromCriteria(array(), array('idResource'), "1=1");
                   if ($nb) {
                     $nbItem=count($nb);
                   }
                   $listItem=$nb;
                } else {
                    $obj=new $item();
                    $where = "1=1";
                    $nbItem=$obj->countSqlElementsFromCriteria(null,$where);
                    $listItem=$obj->getSqlElementsFromCriteria(null,null,$where,null,false,null,$limitRow);
                }
                if ($nbItem==0 or ($item=='User' and $nbItem<=2) ) {
                 $countColor = 'lightgrey';
                } else {
                 $countColor = 'green';
                 $progress++;
                }
                
                echo '  <td title="'.$title.'" style="width:32px;height:32px;"><div style="border-radius:3px;background-color:'.$countColor.';color:white;text-align:center;">';
                echo '    <div style="line-height: 32px;font-size:15px;font-weight:bold">'.$nbItem.'</div>';
                echo '  </div></td>';
                echo '  <td class="simple-grid__header" style="padding: unset;">';
                echo '    <div style="text-align:left;padding-left:15px;cursor:pointer;" onClick="loadMenuBar'.(($is_object)?'Object':'Item').'(\'' . $item .  '\',null,\'bar\');">'.i18n('menu'.$item).'</div>';
                echo '  </td>';
                
                echo '  <td title="'.i18n('sectionHelp').'" style="width:32px;height:32px;">';
                echo '   <div class="imageColorNewGui iconHelpMenuStartGuide iconSize22" id="'.$item.'" style="cursor:pointer ;margin-left:10px;" onclick="showHelp(\''.$item.'\');"></div></td>';
                
                echo '  </tr>';
                $help=i18n("startGuide".$item);
                if (pq_substr($help,0,1)!='[') {
                  i18n("startGuide".$item);
                }
                echo '<tr><td style="padding:10px 0px 10px;font-size:12px;font-style: italic;" colspan="3">';
                if($nbItem > 0){
                  echo '<div style="width:100%;height:75px;overflow-y:auto;">'.$help.'</div>';
                  echo '</td></tr>';
                  echo '<tr><td colspan="3"><div style="width:100%;height:250px;overflow-y:auto;overflow-x: hidden;border-radius:15px;border: 1px solid #CCCCCC">';
                  echo '<table style="margin:15px;width: 100%;color:#AAAAAA">';
                  foreach ($listItem as $id=>$obj){
                    $name = '';
                    if(is_object($obj) and property_exists(get_class($obj), 'name')){
                      $name = '#'.$obj->id.' '.$obj->name;
                    }else if(is_object($obj) and property_exists(get_class($obj), 'refType') && property_exists(get_class($obj), 'refId')){
                      $name = '#'.$obj->refId.' '.$obj->refType;
                    }else if($item == 'Planning'){
                      $name = '#'.$id.' '.SqlList::getNameFromId('Project', $id);
                    }else if($item == 'Imputation'){
                      $name = '#'.$id.' '.SqlList::getNameFromId('ResourceAll', $id);
                    }
                    $gotoItem = '';
                    if($item != 'Imputation' and $item != 'Planning'){
                      $canGoto=(securityCheckDisplayMenu(null, get_class($obj)) and securityGetAccessRightYesNo('menu'.get_class($obj), 'read', $obj)=="YES")?true:false;
                      $gotoObj = get_class($obj);
                      $gotoObjId = $obj->id;
                      if($canGoto){
                        $gotoItem = 'onClick="gotoElement('."'".$gotoObj."','".htmlEncode($gotoObjId)."'".');"';
                      }
                    }
                    if($item == 'Imputation'){
                      $gotoItem='onClick="
                      if (checkFormChangeInProgress()) {
                      return;
                      }
                      var callback = accessImputationCallBack();
                      saveDataToSession(\'userName\','.$id.',false, function() {loadContent(\'../view/imputationMain.php\',\'centerDiv\',null,null,null,null,null,callback);});"';
                    }
                    if($item == 'Planning'){
                      $gotoItem='onClick="loadMenuBar'.(($is_object)?'Object':'Item').'(\'' . $item .  '\',null,\'bar\');"';
                    }
                    echo '<tr class="startGuideListRow" '.$gotoItem.'><td style="width:95%;padding-bottom:10px;text-overflow:ellipsis;cursor:pointer">'.$name.'</td><td style="width:5%;padding-bottom:10px;padding-right:30px;">'.formatSmallButton('Goto', true).'</td><tr>';
                  }
                  if($nbItem >= $limitRow){
                    echo '<tr class="startGuideListRow"><td colspan="3" style="padding-top: 10px;"><div style="text-align:center;margin-right: 10%;background: #FFDDDD;color: #808080;border-radius: 5px;padding: 2px;">'.i18n('limitedDisplay', array($limitRow)).'</div></td><tr>';                  }
                  echo '</table>';
                }else{
                  echo '<div style="width:100%;height:120px;overflow-y:auto;">'.$help.'</div>';
                  echo '</td></tr>';
                  echo '<tr><td colspan="3"><div style="width:100%;min-height:205px;max-height:250px;overflow-y:auto;overflow-x: hidden;border-radius:15px;border: 1px solid #CCCCCC">';
                  echo '<table style="margin:10px;width: 95%;min-height:185px;max-height:230px;"><tr>';
                  echo '  <td align="'.(($item != 'Planning')?'right':'center').'" style="padding-right:5px;">';
                  echo '    <div onClick="loadMenuBar'.(($is_object)?'Object':'Item').'(\'' . $item .  '\',null,\'bar\');">';
                  echo '    <span class="roundedButtonSmall" style="top:0px;display:inline-block;width:64px;height:64px;"><div class="iconButtonAdd imageColorNewGui" style="background-repeat:no-repeat;width:64px;height:64px;background-size:64px 64px">&nbsp;</div></span>';
                  echo '  </div></td>';
                  if($item != 'Planning'){
                    echo '  <td align="left" style="padding-leftp:5px">';
                    echo '    <div onClick="gotoImportData(\''.$item.'\');">';
                    echo '    <span class="roundedButtonSmall" style="top:0px;display:inline-block;width:64px;height:64px;"><div class="iconButtonUpload imageColorNewGui" style="background-repeat:no-repeat;width:64px;height:64px;background-size:64px 64px">&nbsp;</div></span>';
                    echo '  </div></td>';
                  }
                  echo '</tr></table>';
                }
                echo '</div></td></tr>';
                echo '<tr>';
                echo '  <td align="center" style="padding-top:10px" colspan="3">';
                echo '    <table><tr>';
                if($canRead and $nbItem > 0){
                  echo '      <td align="'.(($item != 'Planning')?'right':'center').'" style="padding-right:5px;">';
                  echo '        <div onClick="loadMenuBar'.(($is_object)?'Object':'Item').'(\'' . $item .  '\',null,\'bar\');">'.formatBigButton('Add').'</div></td>';
                  if($item != 'Planning'){
                    echo '      <td align="left" style="padding-leftp:5px">';
                    echo '        <div onClick="gotoImportData(\''.$item.'\');">'.formatBigButton('Upload').'</div></td>';
                  }
                }else{
                  echo '      <td align="right" style="height:32px"></td>';
                  echo '      <td align="left" style="height:32px"></td>';
                }
                echo '    </tr></table>';
                echo '  </td>';
                echo '</tr>';
                echo '</table>';
              echo '</div>';
           echo '</div>';
           $order++;
         }
         echo '</div>';
       echo '</div>';
     echo '</div>';
     echo '<div style="display:none">';
      echo i18n('startGuideFooter');
     echo '</div>';
    echo '</div>';
    echo '</div>';
    echo '<div style="position:absolute; right:10px; top:0px; ">';
    $progressVal=round($progress/$total*100,0);
    echo '<div class="siteH2" style="white-space:nowrap">'.progressFormatter($progressVal,i18n('progress')."&nbsp;:&nbsp; ").'</div>';
    echo '<br/>'.i18n('showThisPageOnStart').'&nbsp;';
    echo '<div dojoType="dijit.form.CheckBox" checked type="checkbox" id="showOnStart">';
    echo '<script type="dojo/method" event="onChange" >';
    echo ' if (this.checked) {';
    echo '   saveUserParameter("startPage", "startGuide.php");';
    echo ' } else {';
    echo '   saveUserParameter("startPage", "today.php");';
    echo '   showInfo(i18n("showThisPageUnckeck"));';
    echo ' }';
    echo '</script>';
    echo '</div>';
    echo '</div>';
  echo '</div>';
}else{
  echo '<div style="height:100%;padding:10px;overflow:auto;position:relative;">';
  echo '<div class="siteH1">'.i18n('startGuideTitle').'</div>';
  echo '<br/>';
  
  echo i18n('startGuideIntro');
  echo '<br/>';
  
  $arrayItem=array('menuEnvironmentalParameter', 'Client','Contact', 'Resource', 'User',
      'menuWork', 'Project', 'Affectation', 'Activity', 'Milestone', 'Planning', 'Imputation', 'Ticket');
  
  $progress=0;
  $total=0;
  echo '<table style="width:100%">';
  foreach ($arrayItem as $item) {
    if (pq_substr($item,0,4)=='menu') {
      echo '<tr class="siteH2">';
      echo '<td colspan="5">';
      echo '<b>'.i18n("startGuideActionMenu").' "'.i18n($item).'"</b>';
      echo '</td></tr>';
      echo '<tr><td colspan="5">';
      echo '<br/>';
      echo '</td></tr>';
    } else {
      $total++;
      $hideAutoloadError=true; // Avoid error message is autoload
      $is_object=SqlElement::class_exists($item,true);
      $hideAutoloadError=false;
      $canRead=(securityGetAccessRightYesNo('menuUser', 'read') == "YES");
      echo '<tr VALIGN="top" style="padding:0;margin:0;white-space:nowrap">';
      echo '<td class="siteH2" style="text-align:right;">&nbsp;&nbsp;&nbsp;'.i18n("startGuideActionCreate")." ".i18n('menu'.$item).'</td>';
      echo '<td style="position: relative; padding-left:10px;top:-15px;width:50px">&nbsp;&nbsp;&nbsp;';
      if ($canRead) {
        echo '<span style="cursor:pointer; position: relative;top:-8px; margin-left:10px;" onClick="loadMenuBar'.(($is_object)?'Object':'Item').'(\'' . $item .  '\',null,\'bar\');" >';
      }
      echo formatIcon($item, 32);
      echo '</span>';
      echo '&nbsp;&nbsp;&nbsp;';
      if ($item=='Planning') {
        $obj=new PlannedWork();
        $nbItem=0;
        $nb=$obj->countGroupedSqlElementsFromCriteria(array(), array('idProject'), "1=1");
        if ($nb) {
          $nbItem=count($nb);
        }
      } else if ($item=='Imputation') {
        $obj=new PlannedWork();
        $nbItem=0;
        $nb=$obj->countGroupedSqlElementsFromCriteria(array(), array('week','idResource'), "1=1");
        if ($nb) {
          $nbItem=count($nb);
        }
      } else {
        $obj=new $item();
        $crit=array();
        if ($item=='Contact' or $item=='Resource' or $item=='User') {
          $crit['is'.$item]='1';
        }
        if ($item=='Project') {
          $crit['isLeaveMngProject']='0';
        }
        $nbItem=$obj->countSqlElementsFromCriteria($crit);
      }
      echo '</td><td style="position: relative; padding-left:10px;top:-5px;width:50px">';
      if ($nbItem==0 or ($item=='User' and $nbItem<=2) ) {
        echo '<img src="css/images/iconStartGuideTodo.png" />&nbsp;&nbsp;&nbsp;</td>';
        echo '<td VALIGN="middle" colspan="3" style="white-space:normal">';
      } else {
        echo '<img src="css/images/iconStartGuideDone.png"/>&nbsp;&nbsp;&nbsp;</td>';
        echo '<td class="siteH2" style="white-space:nowrap;">'.$nbItem." ";
        if ($item=='Planning') {
          echo i18n('plannedProjects');
        } else {
          echo i18n('menu'.$item);
        }
        echo '&nbsp;&nbsp;</td><td VALIGN="middle" style="white-space:normal; color:#a6a0bc;vertical-align:top;padding-top:2px;">';
        $progress++;
      }
      $help=i18n("startGuide".$item);
      if (pq_substr($help,0,1)!='[') {
        echo i18n("startGuide".$item);
      }
      echo '</td></tr>';
      echo '<tr><td colspan="4">&nbsp;</td></tr>';
    }
  }
  echo "</table>";
  
  echo '<br/>';
  
  //echo i18n('startGuideFooter');
  echo '<br/>';
  echo '<br/>';
  echo '<br/>';
  echo '<div style="position:absolute; right:10px; top:0px; ">';
  $progressVal=round($progress/$total*100,0);
  echo '<div class="siteH2" style="white-space:nowrap">'.progressFormatter($progressVal,i18n('progress')."&nbsp;:&nbsp; ").'</div>';
  echo '<br/>'.i18n('showThisPageOnStart').'&nbsp;';
  echo '<div dojoType="dijit.form.CheckBox" checked type="checkbox" id="showOnStart">';
  echo '<script type="dojo/method" event="onChange" >';
  echo ' if (this.checked) {';
  echo '   saveUserParameter("startPage", "startGuide.php");';
  echo ' } else {';
  echo '   saveUserParameter("startPage", "today.php");';
  echo '   showInfo(i18n("showThisPageUnckeck"));';
  echo ' }';
  echo '</script>';
  echo '</div>';
  echo '</div>';
  echo '</div>';
}
 /*
  "*/
?>